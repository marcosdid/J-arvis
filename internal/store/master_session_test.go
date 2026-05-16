package store

import (
	"context"
	"errors"
	"testing"
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
