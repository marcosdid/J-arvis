package mcp_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	gosdk "github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/localhttp"
	"github.com/marcosdid/jarvis/internal/mcp"
	"github.com/marcosdid/jarvis/internal/store"
)

// TestMCP_EndToEnd_CreateThenGet verifies the MCP server works end-to-end
// over real HTTP: creates a task via the SDK client, then retrieves it,
// asserting both have matching shape.
func TestMCP_EndToEnd_CreateThenGet(t *testing.T) {
	ctx := context.Background()

	// 1. Open SQLite in-memory + migrate
	db := newTestStoreDB(t)

	// 2. Build core services
	tasksRepo := store.NewTasksRepo(db)
	projectsRepo := store.NewProjectsRepo(db)
	bus := &events.LazyEmitter{}

	cat := catalog.MustLoad()
	projectsSvc := core.NewProjectsService(projectsRepo, store.NewRepositoriesRepo(db), tasksRepo, bus)
	tasksSvc := core.NewTasksService(tasksRepo, cat, bus, nil, nil, nil, nil)

	// 3. Seed a project (MCP create_task needs a real project_id)
	seedProjectAndTask(t, db, "proj-e2e", "task-seed")

	// 4. Wire MCP onto localhttp
	tok := mcp.NewBearerToken()
	mcpSrv := mcp.NewServer(tasksSvc, projectsSvc, cat, tok)

	localSrv := localhttp.New()
	if err := localSrv.Mount("/api/mcp", mcpSrv.Handler()); err != nil {
		t.Fatalf("mount: %v", err)
	}

	if _, err := localSrv.Start(); err != nil {
		t.Fatalf("start localhttp: %v", err)
	}
	defer localSrv.Stop()

	// 5. Build an MCP client using the SDK's StreamableClientTransport
	baseURL := localSrv.BaseURL()

	streamTransport := &gosdk.StreamableClientTransport{
		Endpoint: baseURL + "/api/mcp",
		HTTPClient: &http.Client{
			Timeout:   10 * time.Second,
			Transport: &authTransport{token: tok.Value()},
		},
		DisableStandaloneSSE: true, // We're not testing server-initiated events
	}

	clientImpl := &gosdk.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	client := gosdk.NewClient(clientImpl, nil)
	sess, err := client.Connect(ctx, streamTransport, nil)
	if err != nil {
		t.Fatalf("client connect: %v", err)
	}
	defer sess.Close()

	// 6. Call create_task
	createArgs := map[string]any{
		"project_id":  "proj-e2e",
		"title":       "e2e-test-task",
		"description": "Created via e2e test",
	}
	createRes, err := sess.CallTool(ctx, &gosdk.CallToolParams{
		Name:      "create_task",
		Arguments: createArgs,
	})
	if err != nil {
		t.Fatalf("create_task call: %v", err)
	}
	if createRes.IsError {
		t.Fatalf("create_task error: %s", extractToolResult(createRes))
	}

	// Parse the create response
	var createdTask taskShape
	if err := json.Unmarshal([]byte(extractToolResult(createRes)), &createdTask); err != nil {
		t.Fatalf("unmarshal create response: %v", err)
	}

	// Verify the created task has expected fields
	if createdTask.ProjectID != "proj-e2e" {
		t.Errorf("created task project_id: expected proj-e2e, got %s", createdTask.ProjectID)
	}
	if createdTask.Title != "e2e-test-task" {
		t.Errorf("created task title: expected e2e-test-task, got %s", createdTask.Title)
	}
	if createdTask.Description != "Created via e2e test" {
		t.Errorf("created task description: expected 'Created via e2e test', got %s", createdTask.Description)
	}
	if createdTask.State != "idea" {
		t.Errorf("created task state: expected idea, got %s", createdTask.State)
	}
	// permission_profile should be set to a non-nil value from the fallback
	if createdTask.PermissionProfile == nil {
		t.Errorf("created task permission_profile: expected non-nil, got nil")
	}

	capturedTaskID := createdTask.ID
	if capturedTaskID == "" {
		t.Fatalf("created task has no ID")
	}

	// 7. Call get_task with the captured ID
	getArgs := map[string]any{
		"task_id": capturedTaskID,
	}
	getRes, err := sess.CallTool(ctx, &gosdk.CallToolParams{
		Name:      "get_task",
		Arguments: getArgs,
	})
	if err != nil {
		t.Fatalf("get_task call: %v", err)
	}
	if getRes.IsError {
		t.Fatalf("get_task error: %s", extractToolResult(getRes))
	}

	// Parse the get response
	var retrievedTask taskShape
	if err := json.Unmarshal([]byte(extractToolResult(getRes)), &retrievedTask); err != nil {
		t.Fatalf("unmarshal get response: %v", err)
	}

	// Verify the retrieved task matches what was created
	if retrievedTask.ID != capturedTaskID {
		t.Errorf("retrieved task ID: expected %s, got %s", capturedTaskID, retrievedTask.ID)
	}
	if retrievedTask.ProjectID != "proj-e2e" {
		t.Errorf("retrieved task project_id: expected proj-e2e, got %s", retrievedTask.ProjectID)
	}
	if retrievedTask.Title != "e2e-test-task" {
		t.Errorf("retrieved task title: expected e2e-test-task, got %s", retrievedTask.Title)
	}
	if retrievedTask.Description != "Created via e2e test" {
		t.Errorf("retrieved task description: expected 'Created via e2e test', got %s", retrievedTask.Description)
	}
	if retrievedTask.State != "idea" {
		t.Errorf("retrieved task state: expected idea, got %s", retrievedTask.State)
	}
	// Compare permission_profile values, not pointers
	createdPP := ""
	if createdTask.PermissionProfile != nil {
		createdPP = *createdTask.PermissionProfile
	}
	retrievedPP := ""
	if retrievedTask.PermissionProfile != nil {
		retrievedPP = *retrievedTask.PermissionProfile
	}
	if createdPP != retrievedPP {
		t.Errorf("retrieved task permission_profile: expected %q, got %q", createdPP, retrievedPP)
	}
}

// TestMCP_EndToEnd_MultipleTools verifies multiple tools can be called in sequence
func TestMCP_EndToEnd_MultipleTools(t *testing.T) {
	ctx := context.Background()

	db := newTestStoreDB(t)
	tasksRepo := store.NewTasksRepo(db)
	projectsRepo := store.NewProjectsRepo(db)
	bus := &events.LazyEmitter{}

	cat := catalog.MustLoad()
	projectsSvc := core.NewProjectsService(projectsRepo, store.NewRepositoriesRepo(db), tasksRepo, bus)
	tasksSvc := core.NewTasksService(tasksRepo, cat, bus, nil, nil, nil, nil)

	// Seed two projects
	seedProjectAndTask(t, db, "proj-a", "task-a")
	seedProjectAndTask(t, db, "proj-b", "task-b")

	tok := mcp.NewBearerToken()
	mcpSrv := mcp.NewServer(tasksSvc, projectsSvc, cat, tok)

	localSrv := localhttp.New()
	if err := localSrv.Mount("/api/mcp", mcpSrv.Handler()); err != nil {
		t.Fatalf("mount: %v", err)
	}

	_, err := localSrv.Start()
	if err != nil {
		t.Fatalf("start localhttp: %v", err)
	}
	defer localSrv.Stop()

	baseURL := localSrv.BaseURL()
	streamTransport := &gosdk.StreamableClientTransport{
		Endpoint: baseURL + "/api/mcp",
		HTTPClient: &http.Client{
			Timeout:   10 * time.Second,
			Transport: &authTransport{token: tok.Value()},
		},
		DisableStandaloneSSE: true,
	}

	client := gosdk.NewClient(&gosdk.Implementation{Name: "test-client", Version: "0.1.0"}, nil)
	sess, err := client.Connect(ctx, streamTransport, nil)
	if err != nil {
		t.Fatalf("client connect: %v", err)
	}
	defer sess.Close()

	// Test list_projects
	listProjRes, err := sess.CallTool(ctx, &gosdk.CallToolParams{
		Name:      "list_projects",
		Arguments: map[string]any{},
	})
	if err != nil {
		t.Fatalf("list_projects call: %v", err)
	}
	if listProjRes.IsError {
		t.Fatalf("list_projects error: %s", extractToolResult(listProjRes))
	}

	var projects []projectShape
	if err := json.Unmarshal([]byte(extractToolResult(listProjRes)), &projects); err != nil {
		t.Fatalf("unmarshal projects: %v", err)
	}
	if len(projects) < 2 {
		t.Errorf("list_projects: expected at least 2 projects, got %d", len(projects))
	}

	// Test get_project
	getProjRes, err := sess.CallTool(ctx, &gosdk.CallToolParams{
		Name:      "get_project",
		Arguments: map[string]any{"project_id": "proj-a"},
	})
	if err != nil {
		t.Fatalf("get_project call: %v", err)
	}
	if getProjRes.IsError {
		t.Fatalf("get_project error: %s", extractToolResult(getProjRes))
	}

	var proj projectShape
	if err := json.Unmarshal([]byte(extractToolResult(getProjRes)), &proj); err != nil {
		t.Fatalf("unmarshal project: %v", err)
	}
	if proj.ID != "proj-a" {
		t.Errorf("get_project: expected proj-a, got %s", proj.ID)
	}

	// Test list_tasks
	listTaskRes, err := sess.CallTool(ctx, &gosdk.CallToolParams{
		Name:      "list_tasks",
		Arguments: map[string]any{"project_id": "proj-a"},
	})
	if err != nil {
		t.Fatalf("list_tasks call: %v", err)
	}
	if listTaskRes.IsError {
		t.Fatalf("list_tasks error: %s", extractToolResult(listTaskRes))
	}

	var tasks []taskShape
	if err := json.Unmarshal([]byte(extractToolResult(listTaskRes)), &tasks); err != nil {
		t.Fatalf("unmarshal tasks: %v", err)
	}
	if len(tasks) < 1 {
		t.Errorf("list_tasks: expected at least 1 task, got %d", len(tasks))
	}
}

// Helper types and functions

type projectShape struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	Path string `json:"path"`
}

type taskShape struct {
	ID                string  `json:"id"`
	ProjectID         string  `json:"project_id"`
	Title             string  `json:"title"`
	Description       string  `json:"description"`
	State             string  `json:"state"`
	Branch            *string `json:"branch"`
	Template          *string `json:"template"`
	PermissionProfile *string `json:"permission_profile"`
}

// authTransport is a custom http.RoundTripper that adds the Bearer token
type authTransport struct {
	token string
}

func (a *authTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	req.Header.Set("Authorization", "Bearer "+a.token)
	return http.DefaultTransport.RoundTrip(req)
}

// extractToolResult extracts the text content from an MCP CallToolResult
func extractToolResult(res *gosdk.CallToolResult) string {
	if len(res.Content) == 0 {
		return ""
	}
	if tc, ok := res.Content[0].(*gosdk.TextContent); ok {
		return tc.Text
	}
	return ""
}

// newTestStoreDB opens a fresh SQLite at t.TempDir() and applies all migrations.
func newTestStoreDB(t *testing.T) *sql.DB {
	t.Helper()
	dbPath := t.TempDir() + "/test.db"
	db, err := store.Open(context.Background(), dbPath)
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	if err := store.Migrate(context.Background(), db); err != nil {
		t.Fatalf("store.Migrate: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

// seedProjectAndTask inserts a project + a single task into the DB.
func seedProjectAndTask(t *testing.T, db *sql.DB, projectID, taskID string) {
	t.Helper()
	now := time.Now()
	if _, err := db.Exec(
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		projectID, projectID, "/tmp/"+projectID, now,
	); err != nil {
		t.Fatalf("seed project: %v", err)
	}
	if _, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at)
		 VALUES (?, ?, ?, 'idea', ?, ?)`,
		taskID, projectID, "seed-"+taskID, now, now,
	); err != nil {
		t.Fatalf("seed task: %v", err)
	}
}
