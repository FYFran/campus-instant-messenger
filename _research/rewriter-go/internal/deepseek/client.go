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
		http:    &http.Client{Timeout: 600 * time.Second},
		cb:      cb,
	}
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatReq struct {
	Model            string    `json:"model"`
	Messages         []Message `json:"messages"`
	Stream           bool      `json:"stream"`
	MaxTokens        int       `json:"max_tokens,omitempty"`
	Thinking         *thinkCfg `json:"thinking,omitempty"`
	Temperature      float64   `json:"temperature,omitempty"`
	TopP             float64   `json:"top_p,omitempty"`
	FrequencyPenalty float64   `json:"frequency_penalty,omitempty"`
	PresencePenalty  float64   `json:"presence_penalty,omitempty"`
}

type thinkCfg struct {
	Type string `json:"type"`
}

func (c *Client) ChatStream(ctx context.Context, messages []Message, model string, maxTokens int, w io.Writer) error {
	// DeepSeek V4 defaults to thinking=enabled. We disable it for Flash/Pro
	// so users don't see internal monologue. Only Ultimate gets reasoning.
	var useThinking *thinkCfg
	apiModel := model
	if model == "deepseek-v4-ultimate" {
		apiModel = "deepseek-v4-pro"
		useThinking = &thinkCfg{Type: "enabled"}
	} else {
		useThinking = &thinkCfg{Type: "disabled"}
	}
	reqBody, err := json.Marshal(chatReq{Model: apiModel, Messages: messages, Stream: true, MaxTokens: maxTokens, Thinking: useThinking, Temperature: 0.7, TopP: 0.9, FrequencyPenalty: 0.3, PresencePenalty: 0.2})
	if err != nil {
		return fmt.Errorf("marshal chat request: %w", err)
	}
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
	defer func() { _ = resp.Body.Close() }()

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

// Chat sends a non-streaming request and returns the assistant's response content.
func (c *Client) Chat(ctx context.Context, messages []Message, model string, maxTokens int) (string, error) {
	type nonStreamResp struct {
		Choices []struct {
			Message struct {
				Content          string `json:"content"`
				ReasoningContent string `json:"reasoning_content"`
			} `json:"message"`
		} `json:"choices"`
	}
	useT := &thinkCfg{Type: "disabled"}
	apiM := model
	if model == "deepseek-v4-ultimate" {
		apiM = "deepseek-v4-pro"
		useT = &thinkCfg{Type: "enabled"}
	}
	reqBody, err := json.Marshal(chatReq{Model: apiM, Messages: messages, Stream: false, MaxTokens: maxTokens, Thinking: useT, Temperature: 0.7, TopP: 0.9, FrequencyPenalty: 0.3, PresencePenalty: 0.2})
	if err != nil {
		return "", fmt.Errorf("marshal chat request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/chat/completions", bytes.NewReader(reqBody))
	if err != nil {
		return "", fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	done, cbErr := c.cb.Allow()
	if cbErr != nil {
		return "", fmt.Errorf("circuit open: %w", cbErr)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		done(err)
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 500 {
		body, _ := io.ReadAll(resp.Body)
		done(fmt.Errorf("deepseek server error %d", resp.StatusCode))
		return "", fmt.Errorf("deepseek error %d: %s", resp.StatusCode, string(body))
	}
	done(nil)

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("deepseek error %d: %s", resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read response: %w", err)
	}

	var result nonStreamResp
	if err := json.Unmarshal(body, &result); err != nil {
		return "", fmt.Errorf("parse response: %w", err)
	}
	if len(result.Choices) == 0 {
		return "", fmt.Errorf("no response from model")
	}

	content := result.Choices[0].Message.Content
	if content == "" {
		// DeepSeek may return reasoning_content in non-streaming mode
		content = result.Choices[0].Message.ReasoningContent
	}
	return content, nil
}
