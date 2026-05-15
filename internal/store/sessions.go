package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

var ErrSessionNotFound = errors.New("session not found")

// Session mirrors the existing `sessions` table row from migration
// 20260101000001_init.sql. JailID and TranscriptPath are reserved for F10.5+;
// F10.4 writes NULL.
type Session struct {
	ID             string     `json:"id"`
	TaskID         string     `json:"task_id"`
	Status         string     `json:"status"`
	PID            *int       `json:"pid"`
	JailID         *string    `json:"-"` // unused in F10.4
	TranscriptPath *string    `json:"-"` // unused in F10.4
	Cwd            string     `json:"cwd"`
	HookToken      string     `json:"-"` // mirror of in-memory; never JSON-exposed
	LastHookAt     *time.Time `json:"last_hook_at"`
	StartedAt      time.Time  `json:"started_at"`
	EndedAt        *time.Time `json:"ended_at"`
}

type SessionsRepo struct {
	db *sql.DB
}

func NewSessionsRepo(db *sql.DB) *SessionsRepo {
	return &SessionsRepo{db: db}
}

const sessionsSelectCols = `id, task_id, status, pid, jail_id, transcript_path,
	cwd, hook_token, last_hook_at, started_at, ended_at`

func scanSession(s interface{ Scan(...any) error }) (Session, error) {
	var w Session
	err := s.Scan(&w.ID, &w.TaskID, &w.Status, &w.PID, &w.JailID, &w.TranscriptPath,
		&w.Cwd, &w.HookToken, &w.LastHookAt, &w.StartedAt, &w.EndedAt)
	return w, err
}

func (r *SessionsRepo) Insert(ctx context.Context, s Session) error {
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO sessions(`+sessionsSelectCols+`)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		s.ID, s.TaskID, s.Status, s.PID, s.JailID, s.TranscriptPath,
		s.Cwd, nullString(s.HookToken), s.LastHookAt, s.StartedAt, s.EndedAt,
	)
	return err
}

func (r *SessionsRepo) GetByID(ctx context.Context, id string) (*Session, error) {
	row := r.db.QueryRowContext(ctx, `SELECT `+sessionsSelectCols+` FROM sessions WHERE id = ?`, id)
	s, err := scanSession(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrSessionNotFound
		}
		return nil, err
	}
	return &s, nil
}

// UpdateStatus returns the previous status and updates the row to next.
// If no row exists, returns ErrSessionNotFound.
func (r *SessionsRepo) UpdateStatus(ctx context.Context, id, next string) (string, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback() }()
	var prev string
	if err := tx.QueryRowContext(ctx, `SELECT status FROM sessions WHERE id = ?`, id).Scan(&prev); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return "", ErrSessionNotFound
		}
		return "", err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE sessions SET status = ? WHERE id = ?`, next, id); err != nil {
		return "", err
	}
	return prev, tx.Commit()
}

func (r *SessionsRepo) BumpLastHookAt(ctx context.Context, id string, at time.Time) error {
	res, err := r.db.ExecContext(ctx, `UPDATE sessions SET last_hook_at = ? WHERE id = ?`, at, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrSessionNotFound
	}
	return nil
}

func (r *SessionsRepo) MarkEnded(ctx context.Context, id, finalStatus string) error {
	now := time.Now()
	res, err := r.db.ExecContext(ctx,
		`UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?`,
		finalStatus, now, id,
	)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrSessionNotFound
	}
	return nil
}

// ListActiveByTask returns sessions for taskID where ended_at IS NULL.
func (r *SessionsRepo) ListActiveByTask(ctx context.Context, taskID string) ([]Session, error) {
	return r.listByTaskWhere(ctx, taskID, `AND ended_at IS NULL`)
}

func (r *SessionsRepo) ListByTask(ctx context.Context, taskID string) ([]Session, error) {
	return r.listByTaskWhere(ctx, taskID, ``)
}

func (r *SessionsRepo) listByTaskWhere(ctx context.Context, taskID, extra string) ([]Session, error) {
	// G202 false positive: extra is a compile-time constant from the two
	// callers below ("AND ended_at IS NULL" or ""), never user input.
	q := `SELECT ` + sessionsSelectCols + ` FROM sessions WHERE task_id = ? ` + extra + ` ORDER BY started_at ASC` //nolint:gosec
	rows, err := r.db.QueryContext(ctx, q, taskID)
	if err != nil {
		return nil, err
	}
	defer func() { _ = rows.Close() }()
	out := []Session{}
	for rows.Next() {
		s, err := scanSession(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// nullString turns "" into a SQL NULL for hook_token (UNIQUE WHERE NOT NULL).
func nullString(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// SessionsHookAdapter adapts SessionsRepo to the hooks.SessionUpdater interface.
// Defined in store (not hooks) to avoid a hooks→store import cycle.
type SessionsHookAdapter struct {
	repo *SessionsRepo
}

func NewSessionsHookAdapter(repo *SessionsRepo) *SessionsHookAdapter {
	return &SessionsHookAdapter{repo: repo}
}

func (a *SessionsHookAdapter) UpdateStatus(sid, next string) (string, error) {
	return a.repo.UpdateStatus(context.Background(), sid, next)
}

func (a *SessionsHookAdapter) BumpLastHookAt(sid string) error {
	return a.repo.BumpLastHookAt(context.Background(), sid, time.Now())
}

// Compile-time sanity: the adapter must continue to satisfy whatever shape
// hooks.SessionUpdater takes. We do not import hooks here (would create a
// cycle); main.go's wire-up acts as the runtime verification.
var _ = fmt.Sprintf // keep fmt import even after potential refactors
