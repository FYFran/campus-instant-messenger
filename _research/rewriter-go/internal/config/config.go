// Package config reads all configuration from environment variables.
// Never hardcode secrets.
package config

import (
	"log"
	"os"
	"strings"
)

type Config struct {
	Port            string
	JWTSecret       string
	DeepSeekKey     string
	DeepSeekBaseURL string
	DBPath          string
	XenditAPIKey    string
	XenditWebhookToken string
}

func Load() *Config {
	return &Config{
		Port:              envOr("PORT", "9100"),
		JWTSecret:         requireEnv("JWT_SECRET"),
		DeepSeekKey:       requireEnv("DEEPSEEK_API_KEY"),
		DeepSeekBaseURL:   envOr("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
		DBPath:            envOr("DB_PATH", "/app/new-api/data/tokenline.db"),
		XenditAPIKey:      os.Getenv("XENDIT_API_KEY"),
		XenditWebhookToken: os.Getenv("XENDIT_WEBHOOK_TOKEN"),
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" { return v }
	return def
}

func requireEnv(key string) string {
	v := os.Getenv(key)
	if v == "" { log.Fatalf("FATAL: required environment variable %s is not set", key) }
	return v
}

func checkEnv(keys ...string) {
	var missing []string
	for _, key := range keys {
		if _, ok := os.LookupEnv(key); !ok {
			missing = append(missing, key)
		}
	}
	if len(missing) > 0 {
		log.Fatalf("FATAL: missing required environment variables: %s", strings.Join(missing, ", "))
	}
}
