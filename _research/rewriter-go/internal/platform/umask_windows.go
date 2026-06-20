//go:build windows

package platform

// RestrictUmask is a no-op on Windows (no POSIX umask).
func RestrictUmask() {}
