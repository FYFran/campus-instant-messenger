#!/bin/bash
# Verify: concurrent signup should not create duplicates
cd f:/ClaudeFiles/campus_go
go test -tags=integration -run TestSignupConcurrent ./internal/handlers/