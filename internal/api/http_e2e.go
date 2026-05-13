//go:build e2e_http

package api

import (
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"sync"

	"github.com/marcosdid/jarvis/internal/core"
)

// E2EServer exposes the Wails-bound APIs over HTTP so Playwright can
// drive the UI through a headless browser. Only compiled with build tag
// `e2e_http`. Listens on 127.0.0.1:0 (ephemeral) and prints the port
// to stdout as `E2E_HTTP_PORT=<n>` so harnesses can scrape it.
type E2EServer struct {
	tasks     *TasksAPI
	projects  *ProjectsAPI
	worktrees *WorktreesAPI
	master    *MasterAPI
	mu        sync.Mutex
	listener  net.Listener
}

func NewE2EServer(tasks *TasksAPI, projects *ProjectsAPI, worktrees *WorktreesAPI, master *MasterAPI) *E2EServer {
	return &E2EServer{tasks: tasks, projects: projects, worktrees: worktrees, master: master}
}

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
		var req struct{ ProjectIDs []string `json:"project_ids"` }
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
		var req struct{ ID string `json:"id"` }
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.tasks.Discard(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /e2e/tasks/get", func(w http.ResponseWriter, r *http.Request) {
		var req struct{ ID string `json:"id"` }
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
		var req struct{ ID string `json:"id"` }
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
}
