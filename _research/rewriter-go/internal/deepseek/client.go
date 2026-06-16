package deepseek

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/sony/gobreaker/v2"
)

type Client struct {
	apiKey  string
	baseURL string
	http    *http.Client
	cb      *gobreaker.TwoStepCircuitBreaker[[]byte]
}

func New(apiKey, baseURL string) *Client {
	// Circuit breaker: if DeepSeek fails 5+ times in a row, open circuit for 30s.
	// Protects TokenLine from cascading latency when upstream is degraded.
	cb := gobreaker.NewTwoStepCircuitBreaker[[]byte](gobreaker.Settings{
		Name:        "deepseek-api",
		MaxRequests: 5,
		Interval:    30 * time.Second,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.ConsecutiveFailures >= 3
		},
		OnStateChange: func(name string, from, to gobreaker.State) {
			// State changes are logged by the caller via slog
		},
	})
	return &Client{
		apiKey:  apiKey,
		baseURL: baseURL,
		http:    &http.Client{Timeout: 120 * time.Second},
		cb:      cb,
	}
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatReq struct {
	Model     string    `json:"model"`
	Messages  []Message `json:"messages"`
	Stream    bool      `json:"stream"`
	MaxTokens int       `json:"max_tokens,omitempty"`
}

func (c *Client) ChatStream(ctx context.Context, messages []Message, model string, maxTokens int, w io.Writer) error {
	reqBody, _ := json.Marshal(chatReq{Model: model, Messages: messages, Stream: true, MaxTokens: maxTokens})
	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/chat/completions", bytes.NewReader(reqBody))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	// Circuit-breaker protected HTTP call
	done, cbErr := c.cb.Allow()
	if cbErr != nil {
		return fmt.Errorf("circuit open: %w", cbErr)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		done(err) // mark as failure — trip the circuit
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 500 {
		body, _ := io.ReadAll(resp.Body)
		done(fmt.Errorf("deepseek server error %d", resp.StatusCode)) // trip the circuit
		return fmt.Errorf("deepseek error %d: %s", resp.StatusCode, string(body))
	}

	done(nil) // success — circuit stays closed
	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("deepseek error %d: %s", resp.StatusCode, string(body))
	}
	_, err = io.Copy(w, resp.Body)
	return err
}
