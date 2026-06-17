package handler

import (
	"archive/zip"
	"bytes"
	"encoding/xml"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
)

// UploadHandler extracts text from uploaded files (txt, docx).
// Returns extracted text as JSON — frontend prepends it to chat message.
func UploadHandler(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, 10<<20) // 10MB max
	if err := r.ParseMultipartForm(10 << 20); err != nil {
		writeJSON(w, 400, "File terlalu besar. Maks 10MB.")
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		writeJSON(w, 400, "File tidak ditemukan")
		return
	}
	defer func() { _ = file.Close() }()

	data, err := io.ReadAll(file)
	if err != nil {
		slog.Error("upload read", "error", err)
		writeJSON(w, 500, "Gagal membaca file")
		return
	}

	var text string
	name := strings.ToLower(header.Filename)

	switch {
	case strings.HasSuffix(name, ".txt"):
		text = string(data)
	case strings.HasSuffix(name, ".docx"):
		text, err = extractDocxText(data)
		if err != nil {
			slog.Error("docx extract", "error", err)
			writeJSON(w, 400, "Gagal membaca file .docx. Pastikan format benar.")
			return
		}
	default:
		writeJSON(w, 400, "Format tidak didukung. Gunakan .txt atau .docx.")
		return
	}

	if len(text) > 50000 {
		text = text[:50000] + "\n\n[Dipotong — maks 50.000 karakter]"
	}

	slog.Info("file uploaded", "user", userID, "name", header.Filename, "size", len(data), "text_len", len(text))
	writeJSON(w, 200, map[string]interface{}{
		"filename": header.Filename,
		"text":     text,
		"size":     len(data),
	})
}

// extractDocxText extracts plain text from a .docx file (ZIP containing word/document.xml).
func extractDocxText(data []byte) (string, error) {
	zr, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return "", fmt.Errorf("word/document.xml tidak ditemukan — file bukan docx yang valid")
	}
	for _, f := range zr.File {
		if f.Name == "word/document.xml" {
			rc, err := f.Open()
			if err != nil {
				return "", err
			}
			defer func() { _ = rc.Close() }()
			xmlData, err := io.ReadAll(rc)
			if err != nil {
				return "", err
			}
			return parseDocxXML(xmlData), nil
		}
	}
	return "", err
}

// parseDocxXML extracts text from WordprocessingML XML.
// Strips all XML tags, keeps text content of <w:t> elements.
func parseDocxXML(data []byte) string {
	decoder := xml.NewDecoder(bytes.NewReader(data))
	var buf strings.Builder
	inText := false
	for {
		tok, err := decoder.Token()
		if err != nil {
			break
		}
		switch t := tok.(type) {
		case xml.StartElement:
			if t.Name.Local == "t" {
				inText = true
			}
			// Paragraph break
			if t.Name.Local == "p" && buf.Len() > 0 && !strings.HasSuffix(buf.String(), "\n") {
				buf.WriteByte('\n')
			}
		case xml.EndElement:
			if t.Name.Local == "t" {
				inText = false
			}
		case xml.CharData:
			if inText {
				buf.Write(t)
			}
		}
	}
	return strings.TrimSpace(buf.String())
}
