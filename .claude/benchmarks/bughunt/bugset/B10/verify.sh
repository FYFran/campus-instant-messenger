#!/bin/bash
# Verify: query plan should use index, not seq scan on signups
cd f:/ClaudeFiles/campus_go
go test -run TestListActivitiesSQLSyntax ./internal/handlers/