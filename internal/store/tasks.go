package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var ErrTaskNotFound = errors.New("task not found")

type Task struct {
	ID                string    `json:"id"`
	ProjectID         string    `json:"project_id"`
	Title             string    `json:"title"`
	Description       string    `json:"description"`
	State             string    `json:"state"`
	Branch            *string   `json:"branch"`
	Template          *string   `json:"template"`
	PermissionProfile *string   `json:"permission_profile"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
	ActiveSessionID   *string   `json:"active_session_id"`
}

type TaskFilters struct {
	ProjectIDs []string
	States     []string
}

type CreateTaskInput struct {
	ProjectID         string
	Title             string
	Description       string
	State             string
	Template          *string
	PermissionProfile *string
	Branch            *string
}

type TasksRepo struct {
	db *sql.DB
}

func NewTasksRepo(db *sql.DB) *TasksRepo {
	return &TasksRepo{db: db}
}

const tasksSelect = `SELECT id, project_id, title, description, state, branch, template, permission_profile, created_at, updated_at, NULL AS active_session_id FROM tasks`

func (r *TasksRepo) List(ctx context.Context, f TaskFilters) ([]Task, error) {
	q := tasksSelect
	args := []any{}
	conds := []string{}

	if len(f.ProjectIDs) > 0 {
		placeholders := strings.Repeat("?,", len(f.ProjectIDs))
		placeholders = placeholders[:len(placeholders)-1]
		conds = append(conds, "project_id IN ("+placeholders+")")
		for _, id := range f.ProjectIDs {
			args = append(args, id)
		}
	}
	if len(f.States) > 0 {
		placeholders := strings.Repeat("?,", len(f.States))
		placeholders = placeholders[:len(placeholders)-1]
		conds = append(conds, "state IN ("+placeholders+")")
		for _, s := range f.States {
			args = append(args, s)
		}
	}
	if len(conds) > 0 {
		q += " WHERE " + strings.Join(conds, " AND ")
	}
	q += " ORDER BY created_at DESC"

	rows, err := r.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []Task{}
	for rows.Next() {
		t, err := scanTask(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func (r *TasksRepo) Get(ctx context.Context, id string) (*Task, error) {
	row := r.db.QueryRowContext(ctx, tasksSelect+" WHERE id = ?", id)
	t, err := scanTask(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrTaskNotFound
		}
		return nil, err
	}
	return &t, nil
}

func (r *TasksRepo) Create(ctx context.Context, in CreateTaskInput) (*Task, error) {
	id := uuid.NewString()
	now := time.Now().UTC()
	state := in.State
	if state == "" {
		state = "idea"
	}
	_, err := r.db.ExecContext(ctx, `INSERT INTO tasks
		(id, project_id, title, description, state, branch, template, permission_profile, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		id, in.ProjectID, in.Title, in.Description, state, in.Branch, in.Template, in.PermissionProfile, now, now)
	if err != nil {
		return nil, fmt.Errorf("insert task: %w", err)
	}
	return &Task{
		ID:                id,
		ProjectID:         in.ProjectID,
		Title:             in.Title,
		Description:       in.Description,
		State:             state,
		Branch:            in.Branch,
		Template:          in.Template,
		PermissionProfile: in.PermissionProfile,
		CreatedAt:         now,
		UpdatedAt:         now,
	}, nil
}

func (r *TasksRepo) UpdateState(ctx context.Context, id, state string) (*Task, error) {
	now := time.Now().UTC()
	res, err := r.db.ExecContext(ctx,
		`UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?`,
		state, now, id)
	if err != nil {
		return nil, fmt.Errorf("update state: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return nil, ErrTaskNotFound
	}
	return r.Get(ctx, id)
}

// UpdateFields updates title, description, and/or branch fields (not state).
// Any nil pointer means that field is not updated.
func (r *TasksRepo) UpdateFields(ctx context.Context, id string, title *string, description *string, branch *string) (*Task, error) {
	// Build dynamic UPDATE statement for non-nil fields
	updates := []string{}
	args := []any{}

	if title != nil {
		updates = append(updates, "title = ?")
		args = append(args, *title)
	}
	if description != nil {
		updates = append(updates, "description = ?")
		args = append(args, *description)
	}
	if branch != nil {
		updates = append(updates, "branch = ?")
		args = append(args, *branch)
	}

	if len(updates) == 0 {
		// No fields to update, just return the current task
		return r.Get(ctx, id)
	}

	updates = append(updates, "updated_at = ?")
	args = append(args, time.Now().UTC())
	args = append(args, id)

	query := `UPDATE tasks SET ` + strings.Join(updates, ", ") + ` WHERE id = ?`
	res, err := r.db.ExecContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("update fields: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return nil, ErrTaskNotFound
	}
	return r.Get(ctx, id)
}

func (r *TasksRepo) Discard(ctx context.Context, id string) error {
	res, err := r.db.ExecContext(ctx,
		`UPDATE tasks SET state = 'discarded', updated_at = ? WHERE id = ?`,
		time.Now().UTC(), id)
	if err != nil {
		return fmt.Errorf("discard: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrTaskNotFound
	}
	return nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanTask(r rowScanner) (Task, error) {
	var t Task
	err := r.Scan(&t.ID, &t.ProjectID, &t.Title, &t.Description, &t.State,
		&t.Branch, &t.Template, &t.PermissionProfile, &t.CreatedAt, &t.UpdatedAt,
		&t.ActiveSessionID)
	return t, err
}
