package store

import (
	"context"
	"path/filepath"
	"testing"
)

func TestMigrate_AppliesAllUp(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := Open(context.Background(), dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer db.Close()

	if err := Migrate(context.Background(), db); err != nil {
		t.Fatalf("Migrate: %v", err)
	}

	var name string
	if err := db.QueryRow(`SELECT name FROM sqlite_master WHERE type='table' AND name='goose_db_version'`).Scan(&name); err != nil {
		t.Errorf("goose_db_version table not created: %v", err)
	}

	for _, table := range []string{
		"projects", "repositories", "tasks", "worktrees",
		"sessions", "run_instances", "master_session",
	} {
		var got string
		err := db.QueryRow(
			`SELECT name FROM sqlite_master WHERE type='table' AND name=?`, table,
		).Scan(&got)
		if err != nil {
			t.Errorf("table %q not created: %v", table, err)
		}
	}

	for _, idx := range []string{
		"ix_sessions_hook_token", "ix_run_instances_active_task",
	} {
		var got string
		err := db.QueryRow(
			`SELECT name FROM sqlite_master WHERE type='index' AND name=?`, idx,
		).Scan(&got)
		if err != nil {
			t.Errorf("index %q not created: %v", idx, err)
		}
	}
}
