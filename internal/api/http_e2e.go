//go:build e2e_http

package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sync"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/hooks"
)

// E2EServer exposes the Wails-bound APIs over HTTP so Playwright can
// drive the UI through a headless browser. Only compiled with build tag
// `e2e_http`. Listens on 127.0.0.1:0 (ephemeral) and prints the port
// to stdout as `E2E_HTTP_PORT=<n>` so harnesses can scrape it.
type E2EServer struct {
	tasks     *TasksAPI
	projects  *ProjectsAPI
	worktrees *WorktreesAPI
	sessions  *SessionsAPI
	master    *MasterAPI
	hookBase  string
	tokenReg  *hooks.TokenRegistry
	mu        sync.Mutex
	listener  net.Listener
}

func NewE2EServer(tasks *TasksAPI, projects *ProjectsAPI, worktrees *WorktreesAPI, sessions *SessionsAPI, master *MasterAPI) *E2EServer {
	return &E2EServer{tasks: tasks, projects: projects, worktrees: worktrees, sessions: sessions, master: master}
}

// SetHookBase tells the test harness where the hook server is so simulate_hook
// can replay HTTP calls. Set from cmd/jarvis-e2e-http main after hookServer.Start().
func (s *E2EServer) SetHookBase(base string) { s.hookBase = base }

// SetTokenRegistry wires the in-memory hook-token registry so the
// /e2e/sessions/__token debug route can resolve session_id → token.
// E2E_HTTP build only; never exposed in production.
func (s *E2EServer) SetTokenRegistry(reg *hooks.TokenRegistry) { s.tokenReg = reg }

func (s *E2EServer) Start() (int, error) {
	mux := http.NewServeMux()
	s.mount(mux)

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	s.listener = ln
	port := ln.Addr().(*net.TCPAddr).Port
	fmt.Printf("E2E_HTTP_PORT=%d\n", port)
	go func() { _ = http.Serve(ln, withCORS(mux)) }()
	return port, nil
}

func (s *E2EServer) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.listener != nil {
		_ = s.listener.Close()
		s.listener = nil
	}
}

func withCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		h.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, err error) {
	w.WriteHeader(status)
	writeJSON(w, map[string]string{"error": err.Error()})
}

func (s *E2EServer) mount(mux *http.ServeMux) {
	mux.HandleFunc("POST /e2e/tasks/list", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ProjectIDs []string `json:"project_ids"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.tasks.List(req.ProjectIDs)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/tasks/create", func(w http.ResponseWriter, r *http.Request) {
		var in CreateTaskInput
		if err := json.NewDecoder(r.Body).Decode(&in); err != nil {
			writeErr(w, 400, err)
			return
		}
		out, err := s.tasks.Create(in)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/tasks/patch", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID    string         `json:"id"`
			Patch PatchTaskInput `json:"patch"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeErr(w, 400, err)
			return
		}
		out, err := s.tasks.Patch(req.ID, req.Patch)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/tasks/discard", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.tasks.Discard(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /e2e/tasks/get", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.tasks.Get(req.ID)
		if err != nil {
			writeErr(w, 404, err)
			return
		}
		writeJSON(w, out)
	})

	mux.HandleFunc("POST /e2e/projects/list", func(w http.ResponseWriter, _ *http.Request) {
		out, err := s.projects.List()
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/projects/create", func(w http.ResponseWriter, r *http.Request) {
		var req core.CreateProjectInput
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.projects.Create(req)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/projects/delete", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.projects.Delete(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	mux.HandleFunc("POST /e2e/master/status", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, s.master.Status())
	})

	mux.HandleFunc("POST /e2e/worktrees/list_by_project", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ProjectID string `json:"project_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.worktrees.ListByProject(req.ProjectID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/worktrees/delete", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.worktrees.Delete(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /e2e/fixtures/init-git", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Name    string   `json:"name"`
			SubDirs []string `json:"sub_dirs,omitempty"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		base := filepath.Join(os.TempDir(), "jarvis-e2e", "projects", req.Name)
		_ = os.RemoveAll(base)
		if len(req.SubDirs) == 0 {
			if err := initGitDir(base); err != nil {
				writeErr(w, 500, err)
				return
			}
		} else {
			if err := os.MkdirAll(base, 0o755); err != nil {
				writeErr(w, 500, err)
				return
			}
			for _, sub := range req.SubDirs {
				if err := initGitDir(filepath.Join(base, sub)); err != nil {
					writeErr(w, 500, err)
					return
				}
			}
		}
		writeJSON(w, map[string]string{"path": base})
	})
	mux.HandleFunc("POST /e2e/fixtures/git-worktree-add", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			RepoPath   string `json:"repo_path"`
			TargetPath string `json:"target_path"`
			Branch     string `json:"branch"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		cmd := exec.Command("git", "-C", req.RepoPath, "worktree", "add", req.TargetPath, "-b", req.Branch)
		var stderr bytes.Buffer
		cmd.Stderr = &stderr
		if err := cmd.Run(); err != nil {
			writeErr(w, 500, fmt.Errorf("git worktree add: %s", stderr.String()))
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	mux.HandleFunc("POST /e2e/sessions/start", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.sessions.Start(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/sessions/stop", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.sessions.Stop(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /e2e/sessions/list_by_task", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.sessions.ListByTask(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/sessions/transcript", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.sessions.GetTranscript(req.ID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /e2e/sessions/simulate_hook", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Event   string         `json:"event"` // Notification|PreToolUse|Stop
			Token   string         `json:"token"`
			Payload map[string]any `json:"payload"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeErr(w, 400, err)
			return
		}
		if s.hookBase == "" {
			writeErr(w, 500, fmt.Errorf("hook base URL not set on E2EServer"))
			return
		}
		body, _ := json.Marshal(req.Payload)
		url := s.hookBase + "/api/hooks/" + req.Event + "/" + req.Token
		res, err := http.Post(url, "application/json", bytes.NewReader(body))
		if err != nil {
			writeErr(w, 502, err)
			return
		}
		defer res.Body.Close()
		// Write status before body: io.Copy would otherwise flush an implicit 200.
		w.WriteHeader(res.StatusCode)
		_, _ = io.Copy(w, res.Body)
	})
	mux.HandleFunc("POST /e2e/sessions/__token", func(w http.ResponseWriter, r *http.Request) {
		// Debug-only: resolve a session_id to its in-memory hook token so
		// Playwright can simulate hook callbacks. e2e_http build only.
		if s.tokenReg == nil {
			writeErr(w, 500, fmt.Errorf("token registry not wired on E2EServer"))
			return
		}
		var req struct {
			SessionID string `json:"session_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		tok := s.tokenReg.FindBySessionID(req.SessionID)
		if tok == "" {
			writeErr(w, 404, fmt.Errorf("no token registered for session %s", req.SessionID))
			return
		}
		writeJSON(w, map[string]string{"token": tok})
	})
}

func initGitDir(p string) error {
	if err := os.MkdirAll(p, 0o755); err != nil {
		return err
	}
	cmds := [][]string{
		{"init", "-q"},
		{"-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "init"},
	}
	for _, args := range cmds {
		cmd := exec.Command("git", append([]string{"-C", p}, args...)...)
		var stderr bytes.Buffer
		cmd.Stderr = &stderr
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("git %v: %s", args, stderr.String())
		}
	}
	return nil
}
