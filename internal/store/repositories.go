package store

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/google/uuid"
)

// RepoSpecInput is what callers (CreateProject in core layer) pass to
// CreateBulk. The store assigns IDs.
type RepoSpecInput struct {
	Name    string
	SubPath string
}

type RepositoriesRepo struct {
	db *sql.DB
}

func NewRepositoriesRepo(db *sql.DB) *RepositoriesRepo {
	return &RepositoriesRepo{db: db}
}

// ListByProject returns repositories ordered by sub_path ASC. This matches
// the Python canonical order — sub_path "." sorts before any letter, so
// monorepo rows lead.
func (r *RepositoriesRepo) ListByProject(ctx context.Context, projectID string) ([]Repository, error) {
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, project_id, name, sub_path FROM repositories WHERE project_id = ? ORDER BY sub_path ASC`,
		projectID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Repository{}
	for rows.Next() {
		var rp Repository
		if err := rows.Scan(&rp.ID, &rp.ProjectID, &rp.Name, &rp.SubPath); err != nil {
			return nil, err
		}
		out = append(out, rp)
	}
	return out, rows.Err()
}

func (r *RepositoriesRepo) GetByID(ctx context.Context, id string) *Repository {
	row := r.db.QueryRowContext(ctx,
		`SELECT id, project_id, name, sub_path FROM repositories WHERE id = ?`, id)
	var rp Repository
	if err := row.Scan(&rp.ID, &rp.ProjectID, &rp.Name, &rp.SubPath); err != nil {
		return nil
	}
	return &rp
}

// CreateBulk inserts all specs in a single transaction. Returns the created
// rows with assigned IDs. Fails atomically on UNIQUE constraint violation.
func (r *RepositoriesRepo) CreateBulk(ctx context.Context, projectID string, specs []RepoSpecInput) ([]Repository, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback() }()

	created := make([]Repository, 0, len(specs))
	for _, s := range specs {
		id := uuid.NewString()
		_, err := tx.ExecContext(ctx,
			`INSERT INTO repositories(id, project_id, name, sub_path, created_at)
			 VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)`,
			id, projectID, s.Name, s.SubPath,
		)
		if err != nil {
			return nil, fmt.Errorf("insert repository (%s, %s): %w", s.Name, s.SubPath, err)
		}
		created = append(created, Repository{ID: id, ProjectID: projectID, Name: s.Name, SubPath: s.SubPath})
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return created, nil
}
