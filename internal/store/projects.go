package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

var ErrProjectNotFound = errors.New("project not found")

type Repository struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	SubPath string `json:"sub_path"`
}

type Project struct {
	ID           string       `json:"id"`
	Name         string       `json:"name"`
	Path         string       `json:"path"`
	CreatedAt    time.Time    `json:"created_at"`
	Repositories []Repository `json:"repositories"`
}

type CreateProjectInput struct {
	Name string `json:"name"`
	Path string `json:"path"`
}

type ProjectsRepo struct {
	db    *sql.DB
	repos *RepositoriesRepo
}

func NewProjectsRepo(db *sql.DB) *ProjectsRepo {
	return &ProjectsRepo{db: db, repos: NewRepositoriesRepo(db)}
}

func (r *ProjectsRepo) List(ctx context.Context) ([]Project, error) {
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, name, path, created_at FROM projects ORDER BY created_at ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []Project{}
	for rows.Next() {
		var p Project
		if err := rows.Scan(&p.ID, &p.Name, &p.Path, &p.CreatedAt); err != nil {
			return nil, err
		}
		repos, err := r.repositoriesFor(ctx, p.ID)
		if err != nil {
			return nil, err
		}
		p.Repositories = repos
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *ProjectsRepo) repositoriesFor(ctx context.Context, projectID string) ([]Repository, error) {
	return r.repos.ListByProject(ctx, projectID)
}

func (r *ProjectsRepo) Get(ctx context.Context, id string) (*Project, error) {
	var p Project
	err := r.db.QueryRowContext(ctx,
		`SELECT id, name, path, created_at FROM projects WHERE id = ?`, id).
		Scan(&p.ID, &p.Name, &p.Path, &p.CreatedAt)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrProjectNotFound
		}
		return nil, err
	}
	repos, err := r.repositoriesFor(ctx, p.ID)
	if err != nil {
		return nil, err
	}
	p.Repositories = repos
	return &p, nil
}

func (r *ProjectsRepo) Create(ctx context.Context, in CreateProjectInput) (*Project, error) {
	id := uuid.NewString()
	now := time.Now().UTC()
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		id, in.Name, in.Path, now)
	if err != nil {
		return nil, fmt.Errorf("insert project: %w", err)
	}
	return &Project{
		ID: id, Name: in.Name, Path: in.Path, CreatedAt: now,
		Repositories: []Repository{},
	}, nil
}

func (r *ProjectsRepo) Delete(ctx context.Context, id string) error {
	res, err := r.db.ExecContext(ctx, `DELETE FROM projects WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("delete project: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrProjectNotFound
	}
	return nil
}
