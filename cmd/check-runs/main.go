package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

func main() {
	home, _ := os.UserHomeDir()
	db, _ := sql.Open("sqlite", filepath.Join(home, ".local/share/jarvis/jarvis.db"))
	defer db.Close()
	tables, _ := db.Query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
	fmt.Println("tables:")
	for tables.Next() {
		var n string
		tables.Scan(&n)
		fmt.Printf("  %s\n", n)
	}
	rows, err := db.Query("SELECT id, task_id, status, started_at, ended_at, error_message FROM run_instances ORDER BY started_at DESC LIMIT 10")
	if err != nil {
		fmt.Println("query err:", err)
		return
	}
	for rows.Next() {
		var id, taskID, status, startedAt string
		var endedAt, errMsg sql.NullString
		rows.Scan(&id, &taskID, &status, &startedAt, &endedAt, &errMsg)
		fmt.Printf("run=%s task=%s status=%s started=%s ended=%v err=%v\n", short(id), short(taskID), status, startedAt, endedAt.String, errMsg.String)
	}
}

func short(s string) string {
	if len(s) < 8 {
		return s
	}
	return s[:8]
}
