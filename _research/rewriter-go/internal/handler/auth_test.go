package handler

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"testing"

	"tokenline/internal/db"
)

func TestRegisterValidation(t *testing.T) {
	database, err := db.Open(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer database.Close()
	if err := db.Migrate(database, "../../sql/schema.sql"); err != nil {
		t.Fatal(err)
	}

	h := &AuthHandler{DB: database, JWTSecret: "test-secret-key-for-unit-tests-123456789012"}

	tests := []struct {
		name       string
		body       map[string]string
		wantStatus int
	}{
		{"valid", map[string]string{"email": "a@t.com", "password": "Abc12345!", "phone": "+6281111111111"}, 200},
		{"weak pw", map[string]string{"email": "b@t.com", "password": "123", "phone": "+6281111111112"}, 400},
		{"no phone", map[string]string{"email": "c@t.com", "password": "Abc12345!"}, 400},
		{"bad email", map[string]string{"email": "notemail", "password": "Abc12345!", "phone": "+6281111111113"}, 400},
		{"short pw", map[string]string{"email": "d@t.com", "password": "Abc1", "phone": "+6281111111114"}, 400},
		{"no upper", map[string]string{"email": "e@t.com", "password": "abc12345!", "phone": "+6281111111115"}, 400},
		{"no digit", map[string]string{"email": "f@t.com", "password": "Abcdefgh!", "phone": "+6281111111116"}, 400},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(tt.body)
			req := httptest.NewRequest("POST", "/api/auth/register", bytes.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			rec := httptest.NewRecorder()
			h.Register(rec, req)
			if rec.Code != tt.wantStatus {
				t.Errorf("Register: got %d, want %d (body: %s)", rec.Code, tt.wantStatus, rec.Body.String())
			}
		})
	}
}

func TestLoginValidation(t *testing.T) {
	database, err := db.Open(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer database.Close()
	if err := db.Migrate(database, "../../sql/schema.sql"); err != nil {
		t.Fatal(err)
	}

	h := &AuthHandler{DB: database, JWTSecret: "test-secret-key-for-unit-tests-123456789012"}
	body, _ := json.Marshal(map[string]string{
		"email": "login@test.com", "password": "Abc12345!", "phone": "+6281111111111",
	})
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/auth/register", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	h.Register(rec, req)
	if rec.Code != 200 {
		t.Fatalf("setup register failed: %d %s", rec.Code, rec.Body.String())
	}

	tests := []struct {
		name       string
		email      string
		password   string
		wantStatus int
	}{
		{"correct", "login@test.com", "Abc12345!", 200},
		{"wrong pw", "login@test.com", "WrongPass!", 401},
		{"not exist", "no@exist.com", "Whatever1!", 401},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(map[string]string{"email": tt.email, "password": tt.password})
			rec := httptest.NewRecorder()
			req := httptest.NewRequest("POST", "/api/auth/login", bytes.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			h.Login(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("got %d, want %d", rec.Code, tt.wantStatus)
			}
		})
	}
}
