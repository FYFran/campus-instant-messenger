package db

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

func Open(path string) (*sql.DB, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return nil, fmt.Errorf("mkdir db dir: %w", err)
	}
	// SQLite WAL mode: only 1 writer at a time regardless of pool size.
	// WAL readers share the OS cache, so 1 conn handles all reads just fine.
	// Multiple write conns cause SQLITE_BUSY / database is locked under load.
	// Perf pragmas: 64MB page cache + 256MB mmap + temp in memory.
	dsn := fmt.Sprintf("file:%s"+
		"?_pragma=journal_mode(WAL)"+
		"&_pragma=foreign_keys(ON)"+
		"&_pragma=busy_timeout(5000)"+
		"&_pragma=synchronous(NORMAL)"+
		"&_pragma=cache_size(-65536)"+
		"&_pragma=mmap_size(268435456)"+
		"&_pragma=temp_store(MEMORY)", path)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	db.SetConnMaxLifetime(0)
	return db, nil
}

func Migrate(db *sql.DB, schemaPath string) error {
	data, err := os.ReadFile(schemaPath)
	if err != nil {
		return fmt.Errorf("read schema: %w", err)
	}
	if _, err := db.Exec(string(data)); err != nil {
		return fmt.Errorf("exec schema: %w", err)
	}
	return nil
}
