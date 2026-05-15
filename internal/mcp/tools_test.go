package mcp

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	gosdk "github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

var testCatalog = catalog.MustLoad()

// fakeTasksRepo provides a minimal in-memory store.TasksRepo replacement.
type fakeTasksRepo struct {
	items map[string]*store.Task
}

func newFakeTasksRepo() *fakeTasksRepo {
	return &fakeTasksRepo{items: make(map[string]*store.Task)}
}

func (f *fakeTasksRepo) List(_ context.Context, filt store.TaskFilters) ([]store.Task, error) {
	out := make([]store.Task, 0, len(f.items))
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

// TestTaskListAndGet verifies that tasks can be listed and retrieved.
func TestTaskListAndGet(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	// Create a test task
	task1 := &store.Task{
		ID: "tsk-1", ProjectID: "proj-1", Title: "Task 1",
		Description: "Desc 1", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	taskRepo.items["tsk-1"] = task1

	// Test list_tasks
	res, err := callToolDirect(ctx, srv.listTasksHandler, map[string]any{})
	if err != nil {
		t.Fatalf("listTasksHandler: %v", err)
	}
	if res.IsError {
		t.Errorf("listTasksHandler IsError: got true, content: %s", extractJSONFromResult(res))
	}

	jsonData := extractJSONFromResult(res)
	var tasks []mcpTask
	if err := json.Unmarshal(jsonData, &tasks); err != nil {
		t.Fatalf("unmarshal list result: %v", err)
	}
	if len(tasks) != 1 || tasks[0].ID != "tsk-1" {
		t.Errorf("list_tasks: expected 1 task, got %d", len(tasks))
	}

	// Test get_task
	res, err = callToolDirect(ctx, srv.getTaskHandler, map[string]any{"task_id": "tsk-1"})
	if err != nil {
		t.Fatalf("getTaskHandler: %v", err)
	}
	if res.IsError {
		t.Errorf("getTaskHandler IsError: got true, content: %s", extractJSONFromResult(res))
	}

	jsonData = extractJSONFromResult(res)
	var task mcpTask
	if err := json.Unmarshal(jsonData, &task); err != nil {
		t.Fatalf("unmarshal get result: %v", err)
	}
	if task.ID != "tsk-1" {
		t.Errorf("get_task: expected tsk-1, got %s", task.ID)
	}
}

// TestTaskListFilterByProject filters tasks by project ID.
func TestTaskListFilterByProject(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	task1 := &store.Task{
		ID: "tsk-1", ProjectID: "proj-1", Title: "Task 1",
		Description: "Desc", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	task2 := &store.Task{
		ID: "tsk-2", ProjectID: "proj-2", Title: "Task 2",
		Description: "Desc", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	taskRepo.items["tsk-1"] = task1
	taskRepo.items["tsk-2"] = task2

	res, err := callToolDirect(ctx, srv.listTasksHandler, map[string]any{"project_id": "proj-1"})
	if err != nil {
		t.Fatalf("listTasksHandler: %v", err)
	}

	jsonData := extractJSONFromResult(res)
	var tasks []mcpTask
	if err := json.Unmarshal(jsonData, &tasks); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}

	if len(tasks) != 1 || tasks[0].ProjectID != "proj-1" {
		t.Errorf("expected 1 task from proj-1, got %d", len(tasks))
	}
}

// TestTaskListFilterByState filters tasks by state.
func TestTaskListFilterByState(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	task1 := &store.Task{
		ID: "tsk-1", ProjectID: "proj-1", Title: "Task 1",
		Description: "Desc", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	task2 := &store.Task{
		ID: "tsk-2", ProjectID: "proj-1", Title: "Task 2",
		Description: "Desc", State: "ready", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	taskRepo.items["tsk-1"] = task1
	taskRepo.items["tsk-2"] = task2

	res, err := callToolDirect(ctx, srv.listTasksHandler, map[string]any{"state": "ready"})
	if err != nil {
		t.Fatalf("listTasksHandler: %v", err)
	}

	jsonData := extractJSONFromResult(res)
	var tasks []mcpTask
	if err := json.Unmarshal(jsonData, &tasks); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}

	if len(tasks) != 1 || tasks[0].State != "ready" {
		t.Errorf("expected 1 task with state ready, got %d", len(tasks))
	}
}

// TestGetTaskNotFound verifies error handling for missing tasks.
func TestGetTaskNotFound(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	res, err := callToolDirect(ctx, srv.getTaskHandler, map[string]any{"task_id": "nonexistent"})
	if err != nil {
		t.Fatalf("getTaskHandler: %v", err)
	}

	if !res.IsError {
		t.Errorf("IsError: expected true, got false")
	}

	jsonData := extractJSONFromResult(res)
	if !contains(string(jsonData), "task not found") {
		t.Errorf("error message should contain 'task not found', got: %s", jsonData)
	}
}

// TestCreateTask verifies task creation with and without templates.
func TestCreateTask(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	// Create with template
	res, err := callToolDirect(ctx, srv.createTaskHandler, map[string]any{
		"project_id": "proj-1",
		"title":      "New Task",
		"template":   "backend",
	})
	if err != nil {
		t.Fatalf("createTaskHandler: %v", err)
	}

	if res.IsError {
		t.Errorf("IsError: got true, content: %s", extractJSONFromResult(res))
	}

	jsonData := extractJSONFromResult(res)
	var task mcpTask
	if err := json.Unmarshal(jsonData, &task); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}

	if task.Title != "New Task" || task.ProjectID != "proj-1" {
		t.Errorf("task shape incorrect: %v", task)
	}
	if task.Template == nil || *task.Template != "backend" {
		t.Errorf("expected template 'backend', got %v", task.Template)
	}
	if task.State != "idea" {
		t.Errorf("expected state 'idea', got %s", task.State)
	}
}

// TestCreateTaskUnknownTemplate verifies error handling for invalid templates.
func TestCreateTaskUnknownTemplate(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	res, err := callToolDirect(ctx, srv.createTaskHandler, map[string]any{
		"project_id": "proj-1",
		"title":      "New Task",
		"template":   "nonexistent",
	})
	if err != nil {
		t.Fatalf("createTaskHandler: %v", err)
	}

	if !res.IsError {
		t.Errorf("IsError: expected true, got false")
	}

	jsonData := extractJSONFromResult(res)
	if !contains(string(jsonData), "unknown template") {
		t.Errorf("error message should contain 'unknown template', got: %s", jsonData)
	}
}

// TestUpdateTask verifies task updates.
func TestUpdateTask(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	task1 := &store.Task{
		ID: "tsk-1", ProjectID: "proj-1", Title: "Old Title",
		Description: "Desc", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	taskRepo.items["tsk-1"] = task1

	res, err := callToolDirect(ctx, srv.updateTaskHandler, map[string]any{
		"task_id": "tsk-1",
		"title":   "New Title",
	})
	if err != nil {
		t.Fatalf("updateTaskHandler: %v", err)
	}

	if res.IsError {
		t.Errorf("IsError: got true, content: %s", extractJSONFromResult(res))
	}

	jsonData := extractJSONFromResult(res)
	var task mcpTask
	if err := json.Unmarshal(jsonData, &task); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}

	if task.Title != "New Title" {
		t.Errorf("expected title 'New Title', got %s", task.Title)
	}
}

// TestDiscardTask verifies task discard.
func TestDiscardTask(t *testing.T) {
	t.Helper()
	ctx := context.Background()

	taskRepo := newFakeTasksRepo()
	taskSvc := core.NewTasksService(taskRepo, testCatalog, &events.LazyEmitter{}, nil, nil)

	tok := NewBearerToken()
	srv := &Server{
		tasks:   taskSvc,
		catalog: testCatalog,
		token:   tok,
		mcp:     gosdk.NewServer(&gosdk.Implementation{Name: "j-arvis-master", Version: "0.1.0"}, nil),
	}

	task1 := &store.Task{
		ID: "tsk-1", ProjectID: "proj-1", Title: "Task 1",
		Description: "Desc", State: "idea", CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	taskRepo.items["tsk-1"] = task1

	res, err := callToolDirect(ctx, srv.discardTaskHandler, map[string]any{"task_id": "tsk-1"})
	if err != nil {
		t.Fatalf("discardTaskHandler: %v", err)
	}

	if res.IsError {
		t.Errorf("IsError: got true, content: %s", extractJSONFromResult(res))
	}

	jsonData := extractJSONFromResult(res)
	var task mcpTask
	if err := json.Unmarshal(jsonData, &task); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}

	if task.State != "discarded" {
		t.Errorf("expected state 'discarded', got %s", task.State)
	}
}

// Helper functions

// callToolDirect invokes a handler function directly with JSON arguments.
func callToolDirect(ctx context.Context, handler gosdk.ToolHandler, args map[string]any) (*gosdk.CallToolResult, error) {
	jsonArgs, _ := json.Marshal(args)
	req := &gosdk.CallToolRequest{
		Params: &gosdk.CallToolParamsRaw{
			Arguments: jsonArgs,
		},
	}
	return handler(ctx, req)
}

// extractJSONFromResult extracts the JSON from a CallToolResult.
func extractJSONFromResult(res *gosdk.CallToolResult) []byte {
	if len(res.Content) == 0 {
		return []byte{}
	}
	if tc, ok := res.Content[0].(*gosdk.TextContent); ok {
		return []byte(tc.Text)
	}
	return []byte{}
}

// contains checks if a string contains a substring.
func contains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
