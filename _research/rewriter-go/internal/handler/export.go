package handler

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log/slog"
	"mime/multipart"
	"net/http"
	"strings"
	"time"
)

type ExportHandler struct{ DB *sql.DB }

type msg struct {
	Role      string
	Content   string
	Model     string
	CreatedAt string
}

type exportReq struct {
	ConversationID int64  `json:"conversation_id"`
	Format         string `json:"format"` // "pdf"
}

func (h *ExportHandler) Export(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}

	var req exportReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.ConversationID == 0 {
		writeJSON(w, 400, "conversation_id diperlukan")
		return
	}
	if req.Format == "" {
		req.Format = "pdf"
	}

	// Verify conversation belongs to user
	var ownerID int64
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT user_id FROM conversations WHERE id=?", req.ConversationID).Scan(&ownerID)
	if err != nil || ownerID != userID {
		writeJSON(w, 404, "Percakapan tidak ditemukan")
		return
	}

	// Get conversation title
	var title string
	h.DB.QueryRowContext(r.Context(),
		"SELECT COALESCE(title,'Percakapan') FROM conversations WHERE id=?", req.ConversationID).Scan(&title)

	// Get messages
	rows, err := h.DB.QueryContext(r.Context(),
		"SELECT role, content, model, created_at FROM messages WHERE conversation_id=? ORDER BY id ASC", req.ConversationID)
	if err != nil {
		slog.Error("export query", "error", err)
		writeJSON(w, 500, "Gagal mengambil pesan")
		return
	}
	defer rows.Close()

	var messages []msg
	for rows.Next() {
		var m msg
		rows.Scan(&m.Role, &m.Content, &m.Model, &m.CreatedAt)
		// Simple markdown-to-HTML conversion
		m.Content = simpleMarkdownToHTML(m.Content)
		messages = append(messages, m)
	}

	// Render HTML
	htmlContent := renderExportHTML(title, messages)

	// Send to Gotenberg
	pdfBytes, err := convertToPDF(htmlContent)
	if err != nil {
		slog.Error("gotenberg convert", "error", err)
		writeJSON(w, 500, "Gagal membuat PDF. Silakan coba lagi.")
		return
	}

	// Return PDF
	filename := fmt.Sprintf("TokenLine-%s-%s.pdf", sanitizeFilename(title), time.Now().Format("20060102"))
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, filename))
	w.Header().Set("Content-Length", fmt.Sprintf("%d", len(pdfBytes)))
	w.Write(pdfBytes)
}

func convertToPDF(html string) ([]byte, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	// Add index.html file
	part, err := writer.CreateFormFile("files", "index.html")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	part.Write([]byte(html))

	// Add options
	writer.WriteField("marginTop", "0.5")
	writer.WriteField("marginBottom", "0.5")
	writer.WriteField("marginLeft", "0.5")
	writer.WriteField("marginRight", "0.5")
	writer.WriteField("paperWidth", "8.27")  // A4
	writer.WriteField("paperHeight", "11.69") // A4
	writer.WriteField("printBackground", "true")
	writer.Close()

	req, err := http.NewRequest("POST", "http://127.0.0.1:3200/forms/chromium/convert/html", &buf)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("gotenberg request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("gotenberg error %d: %s", resp.StatusCode, string(body))
	}

	return io.ReadAll(resp.Body)
}

func esc(s string) string {
	return template.HTMLEscapeString(s)
}

func renderExportHTML(title string, messages []msg) string {
	now := time.Now().Format("02 Jan 2006 15:04")
	html := `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>` + esc(title) + `</title><style>
body{font-family:Georgia,serif;max-width:700px;margin:40px auto;padding:20px;color:#222;line-height:1.8;font-size:12pt}
h2{font-size:18pt;border-bottom:2px solid #222;padding-bottom:8px;margin-top:30px}
.user{background:#f5f5f5;padding:12px 16px;border-radius:8px;margin:12px 0;color:#444}
.assistant{margin:12px 0;padding:12px 16px;border-left:4px solid #1a1c2c}
.model{font-size:9pt;color:#999;margin-top:4px}
.footer{text-align:center;color:#aaa;font-size:9pt;margin-top:40px;border-top:1px solid #eee;padding-top:20px}
</style></head><body><h2>` + esc(title) + `</h2>`
	for _, m := range messages {
		if m.Role == "user" {
			html += `<div class="user"><strong>Pengguna</strong><br>` + m.Content
		} else {
			html += `<div class="assistant"><strong>TokenLine</strong><br>` + m.Content
		}
		if m.Model != "" {
			html += `<div class="model">Model: ` + esc(m.Model) + `</div>`
		}
		html += `</div>`
	}
	html += `<div class="footer">Dibuat dengan TokenLine — ` + now + `</div></body></html>`
	return html
}

func simpleMarkdownToHTML(s string) string {
	// Bold
	s = strings.ReplaceAll(s, "**", "")
	// Newlines to <br>
	s = strings.ReplaceAll(s, "\n", "<br>")
	return s
}

func sanitizeFilename(s string) string {
	s = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			return r
		}
		return '-'
	}, s)
	if len(s) > 50 {
		s = s[:50]
	}
	return strings.Trim(s, "-")
}
