package logger

import (
	"fmt"
	"log/slog"
	"os"
)

// std is the shared slog instance for drop-in log.Printf replacement.
// Outputs JSON to stderr — compatible with container log collectors.
var std = slog.New(slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{
	Level: slog.LevelInfo,
}))

// Printf is a drop-in replacement for log.Printf. Outputs JSON with
// the message and caller info. Existing log.Printf calls work unchanged.
func Printf(format string, v ...any) {
	msg := fmt.Sprintf(format, v...)
	std.Info(msg, "logger", "stdlog")
}

// Println is a drop-in replacement for log.Println.
func Println(v ...any) {
	msg := fmt.Sprint(v...)
	std.Info(msg, "logger", "stdlog")
}

// Fatal is a drop-in replacement for log.Fatal. Outputs JSON then exits.
func Fatal(v ...any) {
	std.Error(fmt.Sprint(v...), "logger", "stdlog", "fatal", true)
	os.Exit(1)
}

// Fatalf is a drop-in replacement for log.Fatalf. Outputs JSON then exits.
func Fatalf(format string, v ...any) {
	msg := fmt.Sprintf(format, v...)
	std.Error(msg, "logger", "stdlog", "fatal", true)
	os.Exit(1)
}
