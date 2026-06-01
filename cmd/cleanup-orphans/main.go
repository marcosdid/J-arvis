// cleanup-orphans is a one-shot maintenance command: it removes from the
// J-arvis SQLite DB all worktree rows that have no task_id. These rows were
// inserted by the pre-F11.9 SyncProjectWorktrees behavior, which imported
// every worktree returned by `git worktree list` as a fake orphan.
//
// IMPORTANT: this only touches the DB. It never runs `git worktree remove`
// or touches the user's actual git worktrees on disk.
//
// Run with the J-arvis app NOT running (SQLite single-writer):
//
//	pkill -9 -f build/bin/jarvis
//	go run ./cmd/cleanup-orphans
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

func main() {
	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatalf("UserHomeDir: %v", err)
	}
	dbPath := filepath.Join(home, ".local/share/jarvis/jarvis.db")
	if _, err := os.Stat(dbPath); err != nil {
		log.Fatalf("DB not found at %s: %v", dbPath, err)
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		log.Fatalf("open DB: %v", err)
	}
	defer db.Close()

	ctx := context.Background()
	res, err := db.ExecContext(ctx, "DELETE FROM worktrees WHERE task_id IS NULL")
	if err != nil {
		log.Fatalf("DELETE failed: %v", err)
	}
	n, _ := res.RowsAffected()
	fmt.Printf("deleted %d orphan worktree row(s) from %s\n", n, dbPath)
}
