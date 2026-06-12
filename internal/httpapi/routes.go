package httpapi

import (
	"encoding/json"
	"net/http"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/core"
)

// Deps carries every Wails-bound API the HTTP layer exposes. Nil members
// are allowed in tests; production wires all of them (main.go).
type Deps struct {
	Token     string
	Tasks     *api.TasksAPI
	Projects  *api.ProjectsAPI
	Worktrees *api.WorktreesAPI
	Sessions  *api.SessionsAPI
	Master    *api.MasterAPI
	Runs      *api.RunsAPI
	Bootstrap *api.BootstrapAPI
	Catalog   *api.CatalogAPI
	Health    *api.HealthAPI
	Events    http.Handler // SSEEmitter.Handler() — served INSIDE the mux to inherit CORS+token
}

type Server struct{ deps Deps }

func New(deps Deps) *Server { return &Server{deps: deps} }

// Handler returns the authenticated /api/* mux. CORS mirrors the e2e
// posture (loopback-only listener + token; origin check adds nothing)
// and MUST allow the Authorization header for vite dev/preview.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	s.mount(mux)
	return withCORS(RequireToken(s.deps.Token, mux))
}

func withCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
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

// Content-Type must precede WriteHeader: headers set after the status line
// is written are silently discarded on a real connection.
func writeErr(w http.ResponseWriter, status int, err error) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
}

func (s *Server) mount(mux *http.ServeMux) {
	// Tasks
	mux.HandleFunc("POST /api/tasks/list", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ProjectIDs []string `json:"project_ids"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Tasks.List(req.ProjectIDs)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/tasks/create", func(w http.ResponseWriter, r *http.Request) {
		var in api.CreateTaskInput
		if err := json.NewDecoder(r.Body).Decode(&in); err != nil {
			writeErr(w, 400, err)
			return
		}
		out, err := s.deps.Tasks.Create(in)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/tasks/patch", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID    string             `json:"id"`
			Patch api.PatchTaskInput `json:"patch"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeErr(w, 400, err)
			return
		}
		out, err := s.deps.Tasks.Patch(req.ID, req.Patch)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/tasks/discard", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Tasks.Discard(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /api/tasks/get", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Tasks.Get(req.ID)
		if err != nil {
			writeErr(w, 404, err)
			return
		}
		writeJSON(w, out)
	})

	// Projects
	mux.HandleFunc("POST /api/projects/list", func(w http.ResponseWriter, _ *http.Request) {
		out, err := s.deps.Projects.List()
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/projects/create", func(w http.ResponseWriter, r *http.Request) {
		var req core.CreateProjectInput
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Projects.Create(req)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/projects/delete", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Projects.Delete(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /api/projects/rescan", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Projects.RescanRepositories(req.ID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})

	// Worktrees
	mux.HandleFunc("POST /api/worktrees/list_by_project", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ProjectID string `json:"project_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Worktrees.ListByProject(req.ProjectID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/worktrees/delete", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Worktrees.Delete(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	// Runs
	mux.HandleFunc("POST /api/runs/start", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Runs.Start(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/runs/get", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Runs.Get(req.TaskID)
		if err != nil {
			writeErr(w, 404, err) // no active run → UI maps to null
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/runs/get_latest", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Runs.GetLatest(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		if out == nil {
			w.WriteHeader(http.StatusNoContent) // null latest → UI maps to null
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/runs/stop", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			RunID string `json:"run_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Runs.Stop(req.RunID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	// Bootstrap
	mux.HandleFunc("POST /api/bootstrap/start", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Bootstrap.Start(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/bootstrap/cancel", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Bootstrap.Cancel(req.TaskID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	// Catalog
	mux.HandleFunc("POST /api/catalog/get", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, s.deps.Catalog.Get())
	})

	// Sessions
	mux.HandleFunc("POST /api/sessions/start", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Sessions.Start(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/sessions/stop", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Sessions.Stop(req.ID); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /api/sessions/list_by_task", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			TaskID string `json:"task_id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Sessions.ListByTask(req.TaskID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/sessions/transcript", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			ID string `json:"id"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		out, err := s.deps.Sessions.GetTranscript(req.ID)
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})

	// Master
	mux.HandleFunc("POST /api/master/status", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, s.deps.Master.Status())
	})
	mux.HandleFunc("POST /api/master/start", func(w http.ResponseWriter, _ *http.Request) {
		out, err := s.deps.Master.Start()
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})
	mux.HandleFunc("POST /api/master/stop", func(w http.ResponseWriter, _ *http.Request) {
		if err := s.deps.Master.Stop(); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /api/master/send", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Data string `json:"data"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Master.Send(req.Data); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("POST /api/master/resize", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Rows uint16 `json:"rows"`
			Cols uint16 `json:"cols"`
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		if err := s.deps.Master.Resize(req.Rows, req.Cols); err != nil {
			writeErr(w, 500, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	// Health
	mux.HandleFunc("POST /api/health/snapshot", func(w http.ResponseWriter, _ *http.Request) {
		out, err := s.deps.Health.Snapshot()
		if err != nil {
			writeErr(w, 500, err)
			return
		}
		writeJSON(w, out)
	})

	// Events (SSE) — nil-guarded: ServeMux.Handle(nil) panics
	if s.deps.Events != nil {
		mux.Handle("GET /api/events", s.deps.Events)
	}
}
