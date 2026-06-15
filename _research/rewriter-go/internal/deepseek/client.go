package deepseek

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	apiKey  string
	baseURL string
	http    *http.Client
}

func New(apiKey, baseURL string) *Client {
	return &Client{
		apiKey:  apiKey,
		baseURL: baseURL,
		http:    &http.Client{Timeout: 120 * time.Second},
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

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("deepseek error %d: %s", resp.StatusCode, string(body))
	}
	_, err = io.Copy(w, resp.Body)
	return err
}
