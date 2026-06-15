package handler

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

// YunPian (云片) SMS + Voice OTP API.
// SMS:   POST https://sms.yunpian.com/v2/sms/single_send.json
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
		slog.Info("OTP enabled via YunPian (SMS + Voice)")
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

// normalizePhone converts an Indonesian phone to +62xxxxxxxxxx.
func normalizePhone(to string) string {
	to = strings.TrimPrefix(to, "+")
	if len(to) == 0 {
		return "+62"
	}
	if strings.HasPrefix(to, "62") {
		return "+" + to
	}
	if strings.HasPrefix(to, "0") {
		return "+62" + to[1:]
	}
	if strings.HasPrefix(to, "8") {
		return "+62" + to
	}
	return "+" + to
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

// SendSMSOTP sends a 6-digit OTP to an Indonesian phone number via SMS.
func SendSMSOTP(to, otp string) error {
	if ypAPIKey == "" {
		return fmt.Errorf("sms not configured")
	}

	to = normalizePhone(to)
	message := fmt.Sprintf("[TokenLine] Kode verifikasi Anda: %s. Jangan berikan kode ini kepada siapapun.", otp)

	form := url.Values{}
	form.Set("apikey", ypAPIKey)
	form.Set("mobile", to)
	form.Set("text", message)

	resp, err := ypHTTP.PostForm("https://sms.yunpian.com/v2/sms/single_send.json", form)
	if err != nil {
		slog.Error("sms send failed", "error", err)
		return err
	}
	defer resp.Body.Close()

	var result struct {
		Code int     `json:"code"`
		Msg  string  `json:"msg"`
		Fee  float64 `json:"fee"`
		Sid  int64   `json:"sid"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if result.Code != 0 {
		slog.Error("sms api error", "code", result.Code, "msg", result.Msg)
		return fmt.Errorf("SMS gagal: %s", result.Msg)
	}

	slog.Info("SMS OTP sent", "to", to, "fee", result.Fee)
	return nil
}

// SendVoiceOTP calls the phone and reads the OTP code aloud.
// Voice calls have near-100% delivery rate — fallback when SMS fails.
func SendVoiceOTP(to, code string) error {
	if ypAPIKey == "" {
		return fmt.Errorf("voice not configured")
	}

	to = normalizePhone(to)

	form := url.Values{}
	form.Set("apikey", ypAPIKey)
	form.Set("mobile", to)
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
	json.NewDecoder(resp.Body).Decode(&result)

	if result.Sid == "" {
		return fmt.Errorf("voice call gagal: tidak ada respon")
	}

	slog.Info("Voice OTP call placed", "to", to, "fee", result.Fee)
	return nil
}
