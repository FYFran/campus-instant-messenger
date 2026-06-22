#!/bin/bash
# Verify: empty DB should return 200, not 500
# Run: DATABASE_URL=postgres://... bash verify.sh
cd f:/ClaudeFiles/campus_go
go test -tags=integration -run TestListActivitiesEmptyDB ./internal/handlers/