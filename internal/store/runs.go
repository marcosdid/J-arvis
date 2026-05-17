package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"
)

var ErrRunNotFound = errors.New("run not found")

type Run struct {
	ID             string     `json:"id"`
	TaskID         string     `json:"task_id"`
	Status         string     `json:"status"`
	Cwd            string     `json:"cwd"`
	ManifestPath   string     `json:"manifest_path"`
	PortsJSON      string     `json:"ports_json"`
	ContainersJSON string     `json:"containers_json"`
	NetworkName    string     `json:"network_name"`
	StartedAt      time.Time  `json:"started_at"`
	EndedAt        *time.Time `json:"ended_at"`
	ErrorMessage   string     `json:"error_message"`
}

// Ports parses PortsJSON to a {service: host_port} map.
func (r Run) Ports() map[string]int {
	m := map[string]int{}
	_ = json.Unmarshal([]byte(r.PortsJSON), &m)
	return m
}

// ContainerIDs parses ContainersJSON to a {service: container_id} map.
func (r Run) ContainerIDs() map[string]string {
	m := map[string]string{}
	_ = json.Unmarshal([]byte(r.ContainersJSON), &m)
	return m
}

type RunsRepo struct {
	db *sql.DB
}

func NewRunsRepo(db *sql.DB) *RunsRepo { return &RunsRepo{db: db} }

const runsSelect = `SELECT id, task_id, status, cwd, manifest_path, ports_json,
  containers_json, network_name, started_at, ended_at, error_message
  FROM run_instances`

func (r *RunsRepo) Insert(ctx context.Context, run Run) error {
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO run_instances
		 (id, task_id, status, cwd, manifest_path, ports_json,
		  containers_json, network_name, started_at, ended_at, error_message)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		run.ID, run.TaskID, run.Status, run.Cwd, run.ManifestPath,
		run.PortsJSON, run.ContainersJSON, run.NetworkName,
		run.StartedAt, run.EndedAt, run.ErrorMessage)
	if err != nil {
		return fmt.Errorf("insert run: %w", err)
	}
	return nil
}

func (r *RunsRepo) GetByID(ctx context.Context, id string) (*Run, error) {
	row := r.db.QueryRowContext(ctx, runsSelect+" WHERE id = ?", id)
	return scanRun(row)
}

func (r *RunsRepo) GetActiveByTask(ctx context.Context, taskID string) (*Run, error) {
	row := r.db.QueryRowContext(ctx,
		runsSelect+" WHERE task_id = ? AND ended_at IS NULL", taskID)
	return scanRun(row)
}

func (r *RunsRepo) UpdateStatus(ctx context.Context, id, status string) error {
	_, err := r.db.ExecContext(ctx,
		`UPDATE run_instances SET status = ? WHERE id = ?`, status, id)
	return err
}

func (r *RunsRepo) UpdateContainerIDs(ctx context.Context, id, containersJSON string) error {
	_, err := r.db.ExecContext(ctx,
		`UPDATE run_instances SET containers_json = ? WHERE id = ?`, containersJSON, id)
	return err
}

func (r *RunsRepo) MarkEnded(ctx context.Context, id, finalStatus, reason string) error {
	now := time.Now().UTC()
	_, err := r.db.ExecContext(ctx,
		`UPDATE run_instances SET status = ?, ended_at = ?, error_message = COALESCE(NULLIF(?, ''), error_message) WHERE id = ?`,
		finalStatus, now, reason, id)
	return err
}

func (r *RunsRepo) MarkFailed(ctx context.Context, id, errMsg string) error {
	now := time.Now().UTC()
	_, err := r.db.ExecContext(ctx,
		`UPDATE run_instances SET status = 'failed', ended_at = ?, error_message = ? WHERE id = ?`,
		now, errMsg, id)
	return err
}

func (r *RunsRepo) ListActive(ctx context.Context) ([]*Run, error) {
	rows, err := r.db.QueryContext(ctx, runsSelect+" WHERE ended_at IS NULL ORDER BY started_at DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Run
	for rows.Next() {
		r, err := scanRun(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func scanRun(s interface{ Scan(...any) error }) (*Run, error) {
	var r Run
	err := s.Scan(&r.ID, &r.TaskID, &r.Status, &r.Cwd, &r.ManifestPath,
		&r.PortsJSON, &r.ContainersJSON, &r.NetworkName,
		&r.StartedAt, &r.EndedAt, &r.ErrorMessage)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrRunNotFound
		}
		return nil, err
	}
	return &r, nil
}
