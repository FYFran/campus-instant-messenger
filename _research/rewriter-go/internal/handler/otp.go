package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

// YunPian (云片) SMS + Voice OTP API.
// SMS:   POST https://sms.yunpian.com/v2/sms/single_send.json  (domestic + international, same endpoint)
// Voice: POST https://voice.yunpian.com/v2/voice/send.json

var (
	ypAPIKey string
	ypHTTP   = &http.Client{Timeout: 15 * time.Second}

	// Simple in-memory rate limiter: phone -> last send time
	phoneCooldown   = map[string]time.Time{}
	phoneCooldownMu sync.Mutex
)

// InitOTP loads YunPian credentials from environment.
func InitOTP() {
	ypAPIKey = os.Getenv("YUNPIAN_API_KEY")
	if ypAPIKey == "" {
		slog.Warn("YUNPIAN_API_KEY not set — SMS/voice OTP disabled")
	} else {
		slog.Info("OTP enabled via YunPian (SMS + Voice, ID/MY/SG)")
	}

	// Periodic cleanup of cooldown map to prevent unbounded growth.
	go func() {
		for {
			time.Sleep(30 * time.Minute)
			phoneCooldownMu.Lock()
			for k, v := range phoneCooldown {
				if time.Since(v) > 30*time.Minute {
					delete(phoneCooldown, k)
				}
			}
			phoneCooldownMu.Unlock()
		}
	}()
}

// normalizePhone normalizes a phone number and returns (E.164 number, country code).
// Handles ID (+62), MY (+60), SG (+65) with their local formats.
func normalizePhone(to string) (string, string) {
	to = strings.TrimPrefix(to, "+")

	// Already international format — detect country by prefix
	if strings.HasPrefix(to, "62") {
		return "+" + to, "ID"
	}
	if strings.HasPrefix(to, "60") {
		return "+" + to, "MY"
	}
	if strings.HasPrefix(to, "65") {
		return "+" + to, "SG"
	}

	// Indonesian local formats (most common for our user base)
	if strings.HasPrefix(to, "0") {
		return "+62" + to[1:], "ID"
	}
	if strings.HasPrefix(to, "8") {
		return "+62" + to, "ID"
	}

	// Malaysian local formats: 01x-xxxxxxx → +60 1x-xxxxxxx
	if strings.HasPrefix(to, "01") {
		return "+60" + to[1:], "MY"
	}

	return "+" + to, "ID"
}

// checkCooldown returns true if phone was sent an OTP within cooldown seconds.
func checkCooldown(phone string, cooldownSec int) bool {
	phoneCooldownMu.Lock()
	defer phoneCooldownMu.Unlock()
	last, ok := phoneCooldown[phone]
	if !ok {
		return false
	}
	return time.Since(last) < time.Duration(cooldownSec)*time.Second
}

// setCooldown marks a phone as having been sent an OTP now.
func setCooldown(phone string) {
	phoneCooldownMu.Lock()
	phoneCooldown[phone] = time.Now()
	phoneCooldownMu.Unlock()
}

// SendSMSOTP sends a 6-digit OTP via SMS. Routes to domestic or international API
// based on the phone number's country code.
func SendSMSOTP(to, otp string) error {
	if ypAPIKey == "" {
		return fmt.Errorf("sms not configured")
	}

	phone, country := normalizePhone(to)
	message := smsMessage(country, otp)

	form := url.Values{}
	form.Set("apikey", ypAPIKey)
	form.Set("mobile", phone)
	form.Set("text", message)
	form.Set("callback_url", "https://tokenline.top/api/sms-callback")

	resp, err := ypHTTP.PostForm("https://sms.yunpian.com/v2/sms/single_send.json", form)
	if err != nil {
		slog.Error("sms send failed", "error", err, "country", country)
		return err
	}
	defer resp.Body.Close()

	var result struct {
		Code int     `json:"code"`
		Msg  string  `json:"msg"`
		Fee  float64 `json:"fee"`
		Sid  int64   `json:"sid"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		slog.Warn("sms api response parse failed", "error", err)
		return fmt.Errorf("SMS gagal: response error")
	}

	if result.Code != 0 {
		slog.Error("sms api error", "code", result.Code, "msg", result.Msg, "country", country)
		return fmt.Errorf("SMS gagal: %s", result.Msg)
	}

	slog.Info("SMS OTP sent", "to", phone, "country", country, "fee", result.Fee)
	return nil
}

// smsMessage returns the localized OTP message for a given country.
func smsMessage(country, otp string) string {
	switch country {
	case "MY", "SG":
		return fmt.Sprintf("[TokenLine] Your verification code: %s. Do not share this code with anyone.", otp)
	default:
		return fmt.Sprintf("[TokenLine] Kode verifikasi Anda: %s. Jangan berikan kode ini kepada siapapun.", otp)
	}
}

// SendVoiceOTP calls the phone and reads the OTP code aloud.
// Voice calls have near-100% delivery rate — fallback when SMS fails.
func SendVoiceOTP(to, code string) error {
	if ypAPIKey == "" {
		return fmt.Errorf("voice not configured")
	}

	phone, _ := normalizePhone(to)

	form := url.Values{}
	form.Set("apikey", ypAPIKey)
	form.Set("mobile", phone)
	form.Set("code", code)

	resp, err := ypHTTP.PostForm("https://voice.yunpian.com/v2/voice/send.json", form)
	if err != nil {
		slog.Error("voice send failed", "error", err)
		return err
	}
	defer resp.Body.Close()

	var result struct {
		Count int     `json:"count"`
		Fee   float64 `json:"fee"`
		Sid   string  `json:"sid"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		slog.Warn("voice api response parse failed", "error", err)
		return fmt.Errorf("voice call gagal: response error")
	}

	if result.Sid == "" {
		return fmt.Errorf("voice call gagal: tidak ada respon")
	}

	slog.Info("Voice OTP call placed", "to", phone, "fee", result.Fee)
	return nil
}

// SMSCallback handles YunPian delivery status push notifications.
// YunPian POSTs a JSON array of status objects to this endpoint.
func SMSCallback(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		slog.Warn("sms callback read failed", "error", err)
		http.Error(w, "bad request", 400)
		return
	}
	defer r.Body.Close()

	var reports []struct {
		Sid             int64  `json:"sid"`
		Mobile          string `json:"mobile"`
		ReportStatus    string `json:"report_status"`
		ErrorMsg        string `json:"error_msg"`
		ErrorDetail     string `json:"error_detail"`
		UserReceiveTime string `json:"user_receive_time"`
	}
	if err := json.Unmarshal(body, &reports); err != nil {
		slog.Warn("sms callback parse failed", "body", string(body), "error", err)
		http.Error(w, "bad request", 400)
		return
	}

	for _, rpt := range reports {
		if rpt.ReportStatus == "SUCCESS" {
			slog.Info("SMS delivered", "sid", rpt.Sid, "mobile", rpt.Mobile, "time", rpt.UserReceiveTime)
		} else {
			slog.Warn("SMS failed", "sid", rpt.Sid, "mobile", rpt.Mobile, "error", rpt.ErrorMsg, "detail", rpt.ErrorDetail)
		}
	}

	w.WriteHeader(200)
	w.Write([]byte(`{"code":0}`))
}
