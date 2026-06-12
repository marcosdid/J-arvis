package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

// ---- helpers ----------------------------------------------------------------

func authHeader(token string) string { return "Bearer " + token }

func doRequest(t *testing.T, h http.Handler, method, path, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	var bodyReader io.Reader
	if body != "" {
		bodyReader = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, bodyReader)
	if token != "" {
		req.Header.Set("Authorization", authHeader(token))
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

// ---- fake tasks repo (copied from internal/api/tasks_test.go) ---------------

var testCatalog = catalog.MustLoad()

func newSvc(repo core.TasksRepoInterface, bus events.Emitter,
	wt core.TasksWorktreeCleanupFn, sess core.TasksSessionCleanupFn,
) *core.TasksService {
	return core.NewTasksService(repo, testCatalog, bus, wt, sess, nil, nil)
}

type fakeTasksRepo struct {
	items map[string]*store.Task
}

func newFakeTasksRepo() *fakeTasksRepo {
	return &fakeTasksRepo{items: map[string]*store.Task{}}
}

func (f *fakeTasksRepo) List(_ context.Context, filt store.TaskFilters) ([]store.Task, error) {
	out := []store.Task{}
	for _, t := range f.items {
		if len(filt.ProjectIDs) > 0 {
			match := false
			for _, p := range filt.ProjectIDs {
				if t.ProjectID == p {
					match = true
					break
				}
			}
			if !match {
				continue
			}
		}
		out = append(out, *t)
	}
	return out, nil
}

func (f *fakeTasksRepo) Get(_ context.Context, id string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	return t, nil
}

func (f *fakeTasksRepo) Create(_ context.Context, in store.CreateTaskInput) (*store.Task, error) {
	t := &store.Task{
		ID: "tsk-" + in.Title, ProjectID: in.ProjectID, Title: in.Title,
		Description: in.Description, State: in.State, Branch: in.Branch,
		Template: in.Template, PermissionProfile: in.PermissionProfile,
		CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	f.items[t.ID] = t
	return t, nil
}

func (f *fakeTasksRepo) UpdateState(_ context.Context, id, state string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	t.State = state
	t.UpdatedAt = time.Now()
	return t, nil
}

func (f *fakeTasksRepo) UpdateFields(_ context.Context, id string, title *string, description *string, branch *string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	if title != nil {
		t.Title = *title
	}
	if description != nil {
		t.Description = *description
	}
	if branch != nil {
		t.Branch = branch
	}
	t.UpdatedAt = time.Now()
	return t, nil
}

func (f *fakeTasksRepo) Discard(_ context.Context, id string) error {
	t, ok := f.items[id]
	if !ok {
		return store.ErrTaskNotFound
	}
	t.State = "discarded"
	return nil
}

// ---- fake projects service (copied from internal/api/projects_test.go) ------

type fakeProjectsService struct {
	created []store.Project
}

func (f *fakeProjectsService) List(_ context.Context) ([]store.Project, error) {
	return f.created, nil
}

func (f *fakeProjectsService) Create(_ context.Context, in core.CreateProjectInput) (*store.Project, error) {
	p := store.Project{
		ID: "prj-" + in.Name, Name: in.Name, Path: in.Path,
		CreatedAt: time.Now(), Repositories: []store.Repository{},
	}
	f.created = append(f.created, p)
	return &p, nil
}

func (f *fakeProjectsService) Delete(_ context.Context, id string) error {
	for i, p := range f.created {
		if p.ID == id {
			f.created = append(f.created[:i], f.created[i+1:]...)
			return nil
		}
	}
	return store.ErrProjectNotFound
}

func (f *fakeProjectsService) RescanRepositories(_ context.Context, id string) (*store.Project, error) {
	for i := range f.created {
		if f.created[i].ID == id {
			return &f.created[i], nil
		}
	}
	return nil, store.ErrProjectNotFound
}

// ---- fake runs service -------------------------------------------------------

type fakeRunsSvc struct {
	activeErr error
}

func (f *fakeRunsSvc) StartRun(_ context.Context, _ string) (*store.Run, error) {
	return nil, errors.New("not implemented")
}
func (f *fakeRunsSvc) StopRun(_ context.Context, _ string) error { return nil }
func (f *fakeRunsSvc) GetActiveByTask(_ context.Context, _ string) (*store.Run, error) {
	return nil, f.activeErr
}
func (f *fakeRunsSvc) GetLatestByTask(_ context.Context, _ string) (*store.Run, error) {
	return nil, nil
}
func (f *fakeRunsSvc) ContainerIDFor(_ context.Context, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeRunsSvc) StreamLogs(_ context.Context, _ string, _ io.Writer) error { return nil }

// ---- tests ------------------------------------------------------------------

func TestRoutesRequireAuth(t *testing.T) {
	srv := New(Deps{Token: "s3cret"})
	w := doRequest(t, srv.Handler(), http.MethodPost, "/api/tasks/list", `{}`, "")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("want 401, got %d", w.Code)
	}
}

func TestHealthSnapshotRoute(t *testing.T) {
	health := api.NewHealthAPI(func() (bool, string) { return true, "" })
	srv := New(Deps{Token: "tok", Health: health})
	w := doRequest(t, srv.Handler(), http.MethodPost, "/api/health/snapshot", "", "tok")
	if w.Code != http.StatusOK {
		t.Errorf("want 200, got %d; body: %s", w.Code, w.Body.String())
	}
}

func TestTasksListRoute(t *testing.T) {
	repo := newFakeTasksRepo()
	svc := newSvc(repo, &events.FakeEmitter{}, nil, nil)
	tasksAPI := api.NewTasksAPI(svc)

	// Seed one task through the API surface (same path the route exercises)
	_, err := tasksAPI.Create(api.CreateTaskInput{ProjectID: "p1", Title: "task-one"})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	srv := New(Deps{Token: "tok", Tasks: tasksAPI})
	body, _ := json.Marshal(map[string]any{"project_ids": []string{"p1"}})
	w := doRequest(t, srv.Handler(), http.MethodPost, "/api/tasks/list", string(body), "tok")

	if w.Code != http.StatusOK {
		t.Fatalf("want 200, got %d; body: %s", w.Code, w.Body.String())
	}
	var tasks []any
	if err := json.NewDecoder(w.Body).Decode(&tasks); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(tasks) != 1 {
		t.Errorf("want 1 task, got %d", len(tasks))
	}
}

func TestRunsGetNoActiveRunIs404(t *testing.T) {
	fakeSvc := &fakeRunsSvc{activeErr: store.ErrRunNotFound}
	runsAPI := api.NewRunsAPI(fakeSvc, func() string { return "http://localhost:0" })
	srv := New(Deps{Token: "tok", Runs: runsAPI})

	// Real server on purpose: httptest.NewRecorder records headers set AFTER
	// WriteHeader, masking a writeErr that forgets Content-Type. A real
	// connection discards late headers, so this assertion catches the bug.
	ts := httptest.NewServer(srv.Handler())
	defer ts.Close()

	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/runs/get", strings.NewReader(`{"task_id":"t1"}`))
	if err != nil {
		t.Fatalf("NewRequest: %v", err)
	}
	req.Header.Set("Authorization", authHeader("tok"))
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("Do: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusNotFound {
		raw, _ := io.ReadAll(res.Body)
		t.Errorf("want 404, got %d; body: %s", res.StatusCode, raw)
	}
	if ct := res.Header.Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}

func TestProjectsRescanRoute(t *testing.T) {
	svc := &fakeProjectsService{}
	projectsAPI := api.NewProjectsAPI(svc)
	created, err := projectsAPI.Create(core.CreateProjectInput{Name: "p", Path: "/p"})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	srv := New(Deps{Token: "tok", Projects: projectsAPI})
	body, _ := json.Marshal(map[string]string{"id": created.ID})
	w := doRequest(t, srv.Handler(), http.MethodPost, "/api/projects/rescan", string(body), "tok")

	if w.Code != http.StatusOK {
		t.Fatalf("want 200, got %d; body: %s", w.Code, w.Body.String())
	}
	var got store.Project
	if err := json.NewDecoder(w.Body).Decode(&got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.ID != created.ID {
		t.Errorf("project ID: got %q, want %q", got.ID, created.ID)
	}
}

// TestAllRoutesRegistered drives mux.Handler (pattern matching only, no
// handler invocation — nil-deps safe) against the full F11.1 route table.
// Catches path typos on routes that have no driveable test (master/*).
func TestAllRoutesRegistered(t *testing.T) {
	routes := []string{
		"POST /api/tasks/list",
		"POST /api/tasks/create",
		"POST /api/tasks/patch",
		"POST /api/tasks/discard",
		"POST /api/tasks/get",
		"POST /api/projects/list",
		"POST /api/projects/create",
		"POST /api/projects/delete",
		"POST /api/projects/rescan",
		"POST /api/worktrees/list_by_project",
		"POST /api/worktrees/delete",
		"POST /api/runs/start",
		"POST /api/runs/get",
		"POST /api/runs/get_latest",
		"POST /api/runs/stop",
		"POST /api/bootstrap/start",
		"POST /api/bootstrap/cancel",
		"POST /api/catalog/get",
		"POST /api/sessions/start",
		"POST /api/sessions/stop",
		"POST /api/sessions/list_by_task",
		"POST /api/sessions/transcript",
		"POST /api/master/status",
		"POST /api/master/start",
		"POST /api/master/stop",
		"POST /api/master/send",
		"POST /api/master/resize",
		"POST /api/health/snapshot",
	}

	registeredPattern := func(mux *http.ServeMux, route string) string {
		method, path, _ := strings.Cut(route, " ")
		_, pattern := mux.Handler(httptest.NewRequest(method, path, nil))
		return pattern
	}

	t.Run("all POST routes registered with nil deps", func(t *testing.T) {
		mux := http.NewServeMux()
		New(Deps{Token: "x"}).mount(mux)
		for _, route := range routes {
			if registeredPattern(mux, route) == "" {
				t.Errorf("route %q not registered", route)
			}
		}
	})

	t.Run("GET /api/events registered only when Events provided", func(t *testing.T) {
		withoutEvents := http.NewServeMux()
		New(Deps{Token: "x"}).mount(withoutEvents)
		if got := registeredPattern(withoutEvents, "GET /api/events"); got != "" {
			t.Errorf("events route registered with nil Events: pattern %q", got)
		}

		stub := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {})
		withEvents := http.NewServeMux()
		New(Deps{Token: "x", Events: stub}).mount(withEvents)
		if registeredPattern(withEvents, "GET /api/events") == "" {
			t.Error("events route not registered with Events provided")
		}
	})
}

func TestEventsRouteRegisteredWhenProvided(t *testing.T) {
	stubHandler := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	t.Run("events handler provided → 200", func(t *testing.T) {
		srv := New(Deps{Token: "tok", Events: stubHandler})
		req := httptest.NewRequest(http.MethodGet, "/api/events?token=tok", nil)
		w := httptest.NewRecorder()
		srv.Handler().ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Errorf("want 200, got %d", w.Code)
		}
	})

	t.Run("events handler nil → no panic and 404", func(t *testing.T) {
		srv := New(Deps{Token: "tok", Events: nil})
		req := httptest.NewRequest(http.MethodGet, "/api/events?token=tok", nil)
		w := httptest.NewRecorder()
		// Must not panic
		srv.Handler().ServeHTTP(w, req)
		if w.Code != http.StatusNotFound {
			t.Errorf("want 404, got %d", w.Code)
		}
	})
}

func TestCORSHeadersOnResponse(t *testing.T) {
	health := api.NewHealthAPI(func() (bool, string) { return true, "" })
	srv := New(Deps{Token: "tok", Health: health})
	h := srv.Handler()

	t.Run("response carries CORS headers", func(t *testing.T) {
		w := doRequest(t, h, http.MethodPost, "/api/health/snapshot", "", "tok")
		if got := w.Header().Get("Access-Control-Allow-Origin"); got != "*" {
			t.Errorf("Access-Control-Allow-Origin: got %q, want *", got)
		}
		allowHeaders := w.Header().Get("Access-Control-Allow-Headers")
		if !strings.Contains(allowHeaders, "Authorization") {
			t.Errorf("Access-Control-Allow-Headers %q does not include Authorization", allowHeaders)
		}
	})

	t.Run("OPTIONS preflight → 204 without auth", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodOptions, "/api/health/snapshot", bytes.NewReader(nil))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != http.StatusNoContent {
			t.Errorf("OPTIONS want 204, got %d", w.Code)
		}
	})
}
