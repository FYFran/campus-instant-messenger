package handler

import (
	"database/sql"
	"net/http"
)

type TemplateHandler struct{ DB *sql.DB }

func (h *TemplateHandler) List(w http.ResponseWriter, r *http.Request) {
	rows, err := h.DB.QueryContext(r.Context(),
		"SELECT id, category, title, tier, user_hint FROM templates ORDER BY sort_order")
	if err != nil {
		writeJSON(w, 500, "Gagal mengambil template")
		return
	}
	defer func() { _ = rows.Close() }()

	type tpl struct {
		ID       int    `json:"id"`
		Category string `json:"category"`
		Title    string `json:"title"`
		Tier     string `json:"tier"`
		UserHint string `json:"user_hint"`
	}
	var list []tpl
	for rows.Next() {
		var t tpl
		_ = rows.Scan(&t.ID, &t.Category, &t.Title, &t.Tier, &t.UserHint)
		list = append(list, t)
	}
	if list == nil {
		list = []tpl{}
	}
	writeJSON(w, 200, list)
}
