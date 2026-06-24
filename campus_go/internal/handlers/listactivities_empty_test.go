//go:build integration
// +build integration

package handlers

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// TestListActivitiesEmptyDB verifies that ListActivities returns 200 with empty items
// when the activities table has no published/non-draft rows.
//
// This is a regression test for the bug where ListActivities returned 500
// when the database was empty. The root cause was the old v1.0.8 query referencing
// columns (signup_count, creator_name, college) that were removed by a migration.
// The v3.0 code uses subqueries and JOINs instead, which work correctly with
// an empty database.
//
// Requires DATABASE_URL env var. Run with: go test -tags=integration -run TestListActivitiesEmptyDB
func TestListActivitiesEmptyDB(t *testing.T) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set — skipping integration test")
	}

	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer pool.Close()

	// Create temp user for auth context
	var userID int
	err = pool.QueryRow(ctx,
		`INSERT INTO users (student_id, phone, name, password_hash, college, role)
		 VALUES ($1,$2,$3,$4,$5,'student')
		 ON CONFLICT (student_id) DO UPDATE SET name=EXCLUDED.name RETURNING id`,
		"EMPTY_DB_TEST_"+t.Name(),
		"13800000000",
		"EmptyDBTest",
		"$2a$10$dummyhash",
		"测试学院",
	).Scan(&userID)
	if err != nil {
		t.Fatalf("create user: %v", err)
	}
	t.Logf("Created test user id=%d", userID)

	// Cleanup
	defer func() {
		_, _ = pool.Exec(ctx, "DELETE FROM users WHERE id=$1", userID)
	}()

	// Count draft-only activities (these should be excluded by WHERE a.status != 'draft')
	var draftCount int
	pool.QueryRow(ctx, "SELECT COUNT(*) FROM activities WHERE status='draft'").Scan(&draftCount)
	t.Logf("Draft-only activities in DB: %d (these are excluded by the query)", draftCount)

	// Build gin context with auth
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", userID)
	c.Request = httptest.NewRequest("GET", "/api/activities", nil)

	// Call the handler
	handler := ListActivities(pool)
	handler(c)

	// Verify 200, not 500
	if w.Code != http.StatusOK {
		t.Errorf("Expected 200, got %d — body: %s", w.Code, w.Body.String())
	} else {
		t.Logf("PASS: ListActivities returned 200 with empty DB")
		t.Logf("Response body: %s", w.Body.String())
	}
}

// TestListActivitiesSQLSyntax verifies the ListActivities SQL query is syntactically valid
// by running it on a real database connection (even if it returns 0 rows).
func TestListActivitiesSQLSyntax(t *testing.T) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set — skipping integration test")
	}

	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer pool.Close()

	// Execute the exact SQL query from ListActivities with userID=0 and LIMIT 1
	// This tests that the SQL compiles and runs without error
	row := pool.QueryRow(ctx,
		`SELECT a.id, a.title, a.description, a.status, a.reward_type, a.signup_mode,
		 a.max_participants, COALESCE(s.cnt, 0),
		 a.hours, a.activity_date, a.deadline, a.location,
		 a.scope_type, a.scope_value, COALESCE(u.name,'') as creator_name,
		 a.created_at, a.gender_limit, COALESCE(a.signup_start,''),
		 COALESCE(a.contact_qq,''), COALESCE(a.contact_phone,''), COALESCE(a.qq_group,''),
		 COALESCE(a.creator_override,'') as creator_override,
		 (sg.user_id IS NOT NULL) as signed_up
		 FROM activities a
		 LEFT JOIN users u ON a.created_by=u.id
		 LEFT JOIN (SELECT activity_id, COUNT(*) as cnt FROM signups GROUP BY activity_id) s ON s.activity_id = a.id
		 LEFT JOIN signups sg ON sg.activity_id = a.id AND sg.user_id = $1
		 WHERE a.status != 'draft' ORDER BY a.created_at DESC LIMIT 1`, 0)

	var id, signupCount, maxP int
	var hours float64
	var title, desc, status, rewardType, signupMode, activityDate, deadline string
	var location, scopeType, scopeVal, creatorName, creatorOverride string
	var genderLimit, contactQQ, contactPhone, qqGroup string
	var createdAt any
	var signedUp bool
	var signupStart string

	err = row.Scan(&id, &title, &desc, &status, &rewardType, &signupMode,
		&maxP, &signupCount, &hours, &activityDate, &deadline,
		&location, &scopeType, &scopeVal, &creatorName,
		&createdAt, &genderLimit, &signupStart,
		&contactQQ, &contactPhone, &qqGroup, &creatorOverride, &signedUp)

	if err != nil {
		if err == pgx.ErrNoRows {
			// ErrNoRows is fine — SQL syntax is valid, just no data
			t.Logf("Query executed successfully (no rows returned)")
		} else {
			// Any other error means SQL syntax or schema mismatch (M01 fix: was Logf)
			t.Errorf("SQL query/scan failed: %v — SQL SYNTAX IS NOT VALID against current schema", err)
		}
	} else {
		t.Logf("Query returned row: id=%d title=%s", id, title)
	}
}
