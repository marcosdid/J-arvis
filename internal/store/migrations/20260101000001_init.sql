-- +goose Up
-- +goose StatementBegin
CREATE TABLE projects (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    path         TEXT NOT NULL UNIQUE,
    created_at   DATETIME NOT NULL
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE repositories (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    sub_path     TEXT NOT NULL,
    created_at   DATETIME NOT NULL,
    CONSTRAINT uq_repo_project_subpath UNIQUE (project_id, sub_path)
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE tasks (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    state              TEXT NOT NULL DEFAULT 'idea',
    template           TEXT,
    permission_profile TEXT,
    branch             TEXT,
    created_at         DATETIME NOT NULL,
    updated_at         DATETIME NOT NULL
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE worktrees (
    id            TEXT PRIMARY KEY,
    path          TEXT NOT NULL UNIQUE,
    branch        TEXT,
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    task_id       TEXT REFERENCES tasks(id) ON DELETE SET NULL
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    status          TEXT NOT NULL,
    pid             INTEGER,
    jail_id         TEXT,
    transcript_path TEXT,
    cwd             TEXT NOT NULL,
    hook_token      TEXT,
    last_hook_at    DATETIME,
    started_at      DATETIME NOT NULL,
    ended_at        DATETIME
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE UNIQUE INDEX ix_sessions_hook_token ON sessions(hook_token) WHERE hook_token IS NOT NULL;
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE run_instances (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    cwd             TEXT NOT NULL,
    manifest_path   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    ports_json      TEXT NOT NULL DEFAULT '{}',
    containers_json TEXT NOT NULL DEFAULT '{}',
    network_name    TEXT NOT NULL,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at        DATETIME,
    error_message   TEXT
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE UNIQUE INDEX ix_run_instances_active_task ON run_instances(task_id) WHERE ended_at IS NULL;
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE master_session (
    id                 TEXT PRIMARY KEY CHECK (id = 'singleton'),
    claude_session_id  TEXT NOT NULL,
    pid                INTEGER,
    started_at         DATETIME NOT NULL,
    last_active        DATETIME NOT NULL
);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE IF EXISTS master_session;
-- +goose StatementEnd
-- +goose StatementBegin
DROP INDEX IF EXISTS ix_run_instances_active_task;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS run_instances;
-- +goose StatementEnd
-- +goose StatementBegin
DROP INDEX IF EXISTS ix_sessions_hook_token;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS sessions;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS worktrees;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS tasks;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS repositories;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE IF EXISTS projects;
-- +goose StatementEnd
