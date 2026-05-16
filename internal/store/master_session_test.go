package store

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestMasterSessionRepo_Get_NoRow_ReturnsErrNotFound(t *testing.T) {
	db := newTestDB(t)
	repo := NewMasterSessionRepo(db)
	_, err := repo.Get(context.Background())
	if !errors.Is(err, ErrMasterSessionNotFound) {
		t.Errorf("err=%v, want ErrMasterSessionNotFound", err)
	}
}

func TestMasterSessionRepo_Upsert_InsertOrReplace(t *testing.T) {
	db := newTestDB(t)
	repo := NewMasterSessionRepo(db)
	if err := repo.Upsert(context.Background(), "uuid-1", 1234); err != nil {
		t.Fatalf("first Upsert: %v", err)
	}
	got, err := repo.Get(context.Background())
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.ClaudeSessionID != "uuid-1" {
		t.Errorf("ClaudeSessionID=%q, want uuid-1", got.ClaudeSessionID)
	}
	if got.PID == nil || *got.PID != 1234 {
		t.Errorf("PID=%v, want 1234", got.PID)
	}
	// Second upsert replaces
	if err := repo.Upsert(context.Background(), "uuid-2", 5678); err != nil {
		t.Fatalf("second Upsert: %v", err)
	}
	got, _ = repo.Get(context.Background())
	if got.ClaudeSessionID != "uuid-2" || *got.PID != 5678 {
		t.Errorf("after replace: got=%+v, want uuid-2/5678", got)
	}
}

func TestMasterSessionRepo_ClearPID_KeepsSessionID(t *testing.T) {
	db := newTestDB(t)
	repo := NewMasterSessionRepo(db)
	_ = repo.Upsert(context.Background(), "uuid-1", 1234)
	if err := repo.ClearPID(context.Background()); err != nil {
		t.Fatalf("ClearPID: %v", err)
	}
	got, err := repo.Get(context.Background())
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.ClaudeSessionID != "uuid-1" {
		t.Errorf("session id was cleared; got=%q want uuid-1", got.ClaudeSessionID)
	}
	if got.PID != nil {
		t.Errorf("PID=%v, want nil", got.PID)
	}
}

func TestMasterSessionRepo_Delete_IsIdempotent(t *testing.T) {
	db := newTestDB(t)
	repo := NewMasterSessionRepo(db)
	// Delete on empty table is no-op
	if err := repo.Delete(context.Background()); err != nil {
		t.Errorf("Delete on empty: %v", err)
	}
	_ = repo.Upsert(context.Background(), "uuid-1", 1234)
	if err := repo.Delete(context.Background()); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	_, err := repo.Get(context.Background())
	if !errors.Is(err, ErrMasterSessionNotFound) {
		t.Errorf("after Delete, Get err=%v, want ErrMasterSessionNotFound", err)
	}
}

func TestMasterSessionRepo_CheckConstraint_RejectsNonSingletonID(t *testing.T) {
	db := newTestDB(t)
	now := time.Now().UTC()
	_, err := db.Exec(
		`INSERT INTO master_session (id, claude_session_id, pid, started_at, last_active)
		 VALUES ('other-id', 'x', 1, ?, ?)`,
		now, now)
	if err == nil {
		t.Error("INSERT with id='other-id' succeeded; CheckConstraint should reject")
	}
}
