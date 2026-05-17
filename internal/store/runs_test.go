package store

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"
)

func TestRunsRepo_Insert_GetByID(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	run := Run{
		ID: "run-1", TaskID: "t1", Status: "pending",
		Cwd: "/tmp/wt-1", ManifestPath: "/tmp/wt-1/.orchestrator/run.yml",
		PortsJSON: `{"db":31000}`, NetworkName: "jarvis-run-run-1",
		StartedAt: time.Now().UTC(),
	}
	if err := repo.Insert(context.Background(), run); err != nil {
		t.Fatalf("Insert: %v", err)
	}
	got, err := repo.GetByID(context.Background(), "run-1")
	if err != nil {
		t.Fatalf("GetByID: %v", err)
	}
	if got.Status != "pending" || got.TaskID != "t1" {
		t.Errorf("got=%+v", got)
	}
}

func TestRunsRepo_GetActiveByTask_PartialUniqueIndexRejectsSecondActive(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	r1 := Run{ID: "run-A", TaskID: "t1", Status: "ready", Cwd: "/x", StartedAt: time.Now()}
	if err := repo.Insert(context.Background(), r1); err != nil {
		t.Fatal(err)
	}
	r2 := Run{ID: "run-B", TaskID: "t1", Status: "ready", Cwd: "/y", StartedAt: time.Now()}
	if err := repo.Insert(context.Background(), r2); err == nil {
		t.Fatal("second active run inserted; partial unique index should reject")
	}
}

func TestRunsRepo_UpdateStatus(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	_ = repo.Insert(context.Background(), Run{ID: "run-1", TaskID: "t1", Status: "pending", Cwd: "/x", StartedAt: time.Now()})

	if err := repo.UpdateStatus(context.Background(), "run-1", "building"); err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "run-1")
	if got.Status != "building" {
		t.Errorf("status=%q, want building", got.Status)
	}
}

func TestRunsRepo_MarkEnded_SetsEndedAtAndStatus(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	_ = repo.Insert(context.Background(), Run{ID: "run-1", TaskID: "t1", Status: "ready", Cwd: "/x", StartedAt: time.Now()})

	if err := repo.MarkEnded(context.Background(), "run-1", "stopped", "user_stop"); err != nil {
		t.Fatalf("MarkEnded: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "run-1")
	if got.Status != "stopped" {
		t.Errorf("status=%q, want stopped", got.Status)
	}
	if got.EndedAt == nil {
		t.Error("EndedAt nil after MarkEnded")
	}
}

func TestRunsRepo_ListActive_OnlyReturnsActive(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	seedProjectAndTaskForRuns(t, db, "p2", "t2")
	_ = repo.Insert(context.Background(), Run{ID: "active", TaskID: "t1", Status: "ready", Cwd: "/x", StartedAt: time.Now()})
	_ = repo.Insert(context.Background(), Run{ID: "ended", TaskID: "t2", Status: "stopped", Cwd: "/y", StartedAt: time.Now()})
	_ = repo.MarkEnded(context.Background(), "ended", "stopped", "")

	active, err := repo.ListActive(context.Background())
	if err != nil {
		t.Fatalf("ListActive: %v", err)
	}
	if len(active) != 1 || active[0].ID != "active" {
		t.Errorf("active=%+v, want only [active]", active)
	}
}

func TestRunsRepo_UpdateContainerIDs(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	_ = repo.Insert(context.Background(), Run{ID: "run-1", TaskID: "t1", Status: "ready", Cwd: "/x", StartedAt: time.Now()})

	if err := repo.UpdateContainerIDs(context.Background(), "run-1", `{"db":"cid-a"}`); err != nil {
		t.Fatalf("UpdateContainerIDs: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "run-1")
	if got.ContainersJSON != `{"db":"cid-a"}` {
		t.Errorf("ContainersJSON=%q", got.ContainersJSON)
	}
	cids := got.ContainerIDs()
	if cids["db"] != "cid-a" {
		t.Errorf("ContainerIDs=%+v", cids)
	}
}

func TestRunsRepo_MarkFailed_SetsStatusAndMessage(t *testing.T) {
	db := newTestDB(t)
	repo := NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	_ = repo.Insert(context.Background(), Run{ID: "run-1", TaskID: "t1", Status: "ready", Cwd: "/x", StartedAt: time.Now()})

	if err := repo.MarkFailed(context.Background(), "run-1", "network timeout"); err != nil {
		t.Fatalf("MarkFailed: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "run-1")
	if got.Status != "failed" {
		t.Errorf("status=%q, want failed", got.Status)
	}
	if got.ErrorMessage != "network timeout" {
		t.Errorf("ErrorMessage=%q, want 'network timeout'", got.ErrorMessage)
	}
	if got.EndedAt == nil {
		t.Error("EndedAt nil after MarkFailed")
	}
}

// seedProjectAndTaskForRuns inserts project + task FK row.
func seedProjectAndTaskForRuns(t *testing.T, db *sql.DB, projectID, taskID string) {
	t.Helper()
	now := time.Now()
	if _, err := db.Exec(
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		projectID, projectID, "/tmp/"+projectID, now); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at) VALUES (?, ?, ?, 'idea', ?, ?)`,
		taskID, projectID, "tt", now, now); err != nil {
		t.Fatal(err)
	}
}

var _ = errors.Is // keep import
