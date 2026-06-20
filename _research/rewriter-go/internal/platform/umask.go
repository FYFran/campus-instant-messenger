//go:build !windows

package platform

import "syscall"

// RestrictUmask sets file creation mask to owner-only (0077).
// Must be called BEFORE opening database files.
func RestrictUmask() {
	syscall.Umask(0077)
}
