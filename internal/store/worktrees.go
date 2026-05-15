package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	"github.com/google/uuid"
)

var ErrWorktreeNotFound = errors.New("worktree not found")

// Worktree mirrors the worktrees table row plus convenience-projected
// repository_name (joined from repositories.name).
type Worktree struct {
	ID             string  `json:"id"`
	RepositoryID   string  `json:"repository_id"`
	RepositoryName string  `json:"repository_name"`
	TaskID         *string `json:"task_id"`
	Path           string  `json:"path"`
	Branch         *string `json:"branch"`
}

func (w Worktree) IsOrphan() bool { return w.TaskID == nil }

type WorktreeUpsert struct {
	RepositoryID string
	Path         string
	Branch       *string
	TaskID       *string
}

type WorktreesRepo struct {
	db *sql.DB
}

func NewWorktreesRepo(db *sql.DB) *WorktreesRepo {
	return &WorktreesRepo{db: db}
}

const wtSelectBase = `
	SELECT w.id, w.repository_id, r.name, w.task_id, w.path, w.branch
	FROM worktrees w
	JOIN repositories r ON r.id = w.repository_id`

func scanWorktree(s interface{ Scan(...any) error }) (Worktree, error) {
	var w Worktree
	err := s.Scan(&w.ID, &w.RepositoryID, &w.RepositoryName, &w.TaskID, &w.Path, &w.Branch)
	return w, err
}

func (r *WorktreesRepo) GetByID(ctx context.Context, id string) (*Worktree, error) {
	row := r.db.QueryRowContext(ctx, wtSelectBase+` WHERE w.id = ?`, id)
	w, err := scanWorktree(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrWorktreeNotFound
		}
		return nil, err
	}
	return &w, nil
}

func (r *WorktreesRepo) GetByPath(ctx context.Context, path string) (*Worktree, error) {
	row := r.db.QueryRowContext(ctx, wtSelectBase+` WHERE w.path = ?`, path)
	w, err := scanWorktree(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrWorktreeNotFound
		}
		return nil, err
	}
	return &w, nil
}

func (r *WorktreesRepo) ListByProject(ctx context.Context, projectID string) ([]Worktree, error) {
	rows, err := r.db.QueryContext(ctx, wtSelectBase+`
		WHERE r.project_id = ?
		ORDER BY w.path ASC`, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Worktree{}
	for rows.Next() {
		w, err := scanWorktree(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}

func (r *WorktreesRepo) ListByTask(ctx context.Context, taskID string) ([]Worktree, error) {
	rows, err := r.db.QueryContext(ctx, wtSelectBase+`
		WHERE w.task_id = ?
		ORDER BY w.path ASC`, taskID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Worktree{}
	for rows.Next() {
		w, err := scanWorktree(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}

func (r *WorktreesRepo) ListOrphansByProject(ctx context.Context, projectID string) ([]Worktree, error) {
	rows, err := r.db.QueryContext(ctx, wtSelectBase+`
		WHERE r.project_id = ? AND w.task_id IS NULL
		ORDER BY w.path ASC`, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Worktree{}
	for rows.Next() {
		w, err := scanWorktree(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}

// Upsert: if a row with this path exists, update branch; else insert.
// Returns the row id (existing or new). Used by SyncProjectWorktrees.
func (r *WorktreesRepo) Upsert(ctx context.Context, in WorktreeUpsert) (string, error) {
	existing, err := r.GetByPath(ctx, in.Path)
	if err != nil && !errors.Is(err, ErrWorktreeNotFound) {
		return "", err
	}
	if existing != nil {
		if _, err := r.db.ExecContext(ctx,
			`UPDATE worktrees SET branch = ? WHERE id = ?`,
			in.Branch, existing.ID,
		); err != nil {
			return "", fmt.Errorf("update branch: %w", err)
		}
		return existing.ID, nil
	}
	id := uuid.NewString()
	if _, err := r.db.ExecContext(ctx,
		`INSERT INTO worktrees(id, repository_id, task_id, path, branch) VALUES (?, ?, ?, ?, ?)`,
		id, in.RepositoryID, in.TaskID, in.Path, in.Branch,
	); err != nil {
		return "", fmt.Errorf("insert: %w", err)
	}
	return id, nil
}

func (r *WorktreesRepo) Delete(ctx context.Context, id string) error {
	res, err := r.db.ExecContext(ctx, `DELETE FROM worktrees WHERE id = ?`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrWorktreeNotFound
	}
	return nil
}

// OrphanRow sets task_id = NULL. Used by CleanupForTask when git remove fails.
func (r *WorktreesRepo) OrphanRow(ctx context.Context, id string) error {
	res, err := r.db.ExecContext(ctx, `UPDATE worktrees SET task_id = NULL WHERE id = ?`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrWorktreeNotFound
	}
	return nil
}
