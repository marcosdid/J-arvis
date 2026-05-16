package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

var ErrMasterSessionNotFound = errors.New("master session not found")

type MasterSession struct {
	ClaudeSessionID string    `json:"claude_session_id"`
	PID             *int      `json:"pid"`
	StartedAt       time.Time `json:"started_at"`
	LastActive      time.Time `json:"last_active"`
}

type MasterSessionRepo struct {
	db *sql.DB
}

func NewMasterSessionRepo(db *sql.DB) *MasterSessionRepo {
	return &MasterSessionRepo{db: db}
}

func (r *MasterSessionRepo) Get(ctx context.Context) (*MasterSession, error) {
	row := r.db.QueryRowContext(ctx,
		`SELECT claude_session_id, pid, started_at, last_active
		 FROM master_session WHERE id = 'singleton'`)
	var s MasterSession
	if err := row.Scan(&s.ClaudeSessionID, &s.PID, &s.StartedAt, &s.LastActive); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrMasterSessionNotFound
		}
		return nil, fmt.Errorf("get master_session: %w", err)
	}
	return &s, nil
}

func (r *MasterSessionRepo) Upsert(ctx context.Context, claudeSessionID string, pid int) error {
	now := time.Now().UTC()
	var pidArg any = pid
	if pid == 0 {
		pidArg = nil // sentinel for "no pid yet"
	}
	_, err := r.db.ExecContext(ctx,
		`INSERT OR REPLACE INTO master_session
		 (id, claude_session_id, pid, started_at, last_active)
		 VALUES ('singleton', ?, ?, ?, ?)`,
		claudeSessionID, pidArg, now, now)
	if err != nil {
		return fmt.Errorf("upsert master_session: %w", err)
	}
	return nil
}
