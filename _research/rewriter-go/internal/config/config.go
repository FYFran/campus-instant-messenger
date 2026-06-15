// Package config reads all configuration from environment variables.
// Never hardcode secrets.
package config

import "os"

type Config struct {
	Port            string
	JWTSecret       string
	DeepSeekKey     string
	DeepSeekBaseURL string
	DBPath          string
	DodoAPIKey      string
	DodoProductID   string
	DodoBaseURL     string
	ExchangeRateUSD float64 // USD to IDR rate for revenue display
}

func Load() *Config {
	return &Config{
		Port:            envOr("PORT", "9100"),
		JWTSecret:       requireEnv("JWT_SECRET"),
		DeepSeekKey:     requireEnv("DEEPSEEK_API_KEY"),
		DeepSeekBaseURL: envOr("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
		DBPath:          envOr("DB_PATH", "/app/new-api/data/tokenline.db"),
		DodoAPIKey:      os.Getenv("DODO_API_KEY"),
		DodoProductID:   os.Getenv("DODO_PRODUCT_ID"),
		DodoBaseURL:     envOr("DODO_BASE_URL", "https://test.dodopayments.com"),
		ExchangeRateUSD: 16300,
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func requireEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		panic("missing env: " + key)
	}
	return v
}
