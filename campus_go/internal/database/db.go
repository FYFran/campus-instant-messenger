package database

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func Connect() *pgxpool.Pool {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("DATABASE_URL env var is required — set it before starting the server")
	}
	config, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		log.Fatalf("parse db config: %v", err)
	}
	config.MaxConns = 80 // 峰值并发2000 × 50ms avg RT / 1000 × 1.2系数
	config.MinConns = 20 // 预热，消除冷启动毛刺
	config.MaxConnLifetime = 30 * time.Minute
	config.MaxConnIdleTime = 5 * time.Minute
	config.HealthCheckPeriod = 30 * time.Second

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		log.Fatalf("connect db: %v", err)
	}
	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("ping db: %v", err)
	}
	log.Println("PostgreSQL connected")
	return pool
}
