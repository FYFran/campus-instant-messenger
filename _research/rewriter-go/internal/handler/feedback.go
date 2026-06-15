package handler

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"
)

const maxFeedbackSize = 1_000_000 // 1MB max feedback file, auto-rotate

func FeedbackHandler(w http.ResponseWriter, r *http.Request) {
	var d struct {
		Email    string `json:"email"`
		Kategori string `json:"kategori"`
		Pesan    string `json:"pesan"`
	}
	if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(400)
		w.Write([]byte(`{"message":"Format tidak valid"}`))
		return
	}
	w.Header().Set("Content-Type", "application/json")
	if d.Pesan == "" {
		w.WriteHeader(400)
		w.Write([]byte(`{"message":"Pesan tidak boleh kosong"}`))
		return
	}

	path := "/app/static/feedback.txt"
	// Rotate if file exceeds 1MB
	if info, err := os.Stat(path); err == nil && info.Size() > maxFeedbackSize {
		os.Rename(path, path+".old")
	}

	// Validate field lengths to prevent log injection and disk abuse
	if len(d.Kategori) > 50 { d.Kategori = d.Kategori[:50] }
	if len(d.Email) > 100 { d.Email = d.Email[:100] }
	if len(d.Pesan) > 5000 { d.Pesan = d.Pesan[:5000] }
	// Sanitize newlines to prevent log injection
	d.Kategori = strings.ReplaceAll(d.Kategori, "\n", " ")
	d.Email = strings.ReplaceAll(d.Email, "\n", " ")
	d.Pesan = strings.ReplaceAll(d.Pesan, "\n", "\\n")

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0600)
	if err != nil {
		slog.Error("feedback write", "error", err)
		w.WriteHeader(500)
		w.Write([]byte(`{"ok":false,"message":"Gagal menyimpan feedback"}`))
		return
	}
	line := fmt.Sprintf("%s | %s | %s | %s\n",
		time.Now().Format("2006-01-02 15:04:05"),
		d.Kategori, d.Email, d.Pesan)
	f.WriteString(line)
	f.Close()

	slog.Info("feedback", "kategori", d.Kategori, "email", d.Email)
	w.Write([]byte(`{"ok":true}`))
}
