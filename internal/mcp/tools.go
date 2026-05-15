package mcp

import (
	"context"
	"encoding/json"
	"errors"

	gosdk "github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

// registerTools wires all 7 task/project tools into the SDK server.
func (s *Server) registerTools() {
	s.mcp.AddTool(&gosdk.Tool{
		Name:        "list_projects",
		Description: "List all projects with their ids, names, and paths.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","properties":{}}`)),
	}, s.listProjectsHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "get_project",
		Description: "Get a project by id.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","required":["project_id"],"properties":{"project_id":{"type":"string"}}}`)),
	}, s.getProjectHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "list_tasks",
		Description: "List tasks, optionally filtered by project and/or state.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","properties":{"project_id":{"type":"string"},"state":{"type":"string","enum":["idea","ready","in_progress","review","done","discarded"]}}}`)),
	}, s.listTasksHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "get_task",
		Description: "Get a task by id.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","required":["task_id"],"properties":{"task_id":{"type":"string"}}}`)),
	}, s.getTaskHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "create_task",
		Description: "Create a new task. Optionally with a template (frontend/backend/refactor/bugfix) which auto-derives permission_profile and branch prefix.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","additionalProperties":false,"required":["project_id","title"],"properties":{"project_id":{"type":"string"},"title":{"type":"string"},"description":{"type":"string"},"template":{"type":"string","enum":["frontend","backend","refactor","bugfix"]},"branch":{"type":"string"}}}`)),
	}, s.createTaskHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "update_task",
		Description: "Update task fields. State transitions follow F4 state machine. NOTE: template é snapshot-at-create (F7) — não editável aqui.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","additionalProperties":false,"required":["task_id"],"properties":{"task_id":{"type":"string"},"title":{"type":"string"},"description":{"type":"string"},"state":{"type":"string"},"branch":{"type":"string"}}}`)),
	}, s.updateTaskHandler)

	s.mcp.AddTool(&gosdk.Tool{
		Name:        "discard_task",
		Description: "Move task to discarded state.",
		InputSchema: json.RawMessage([]byte(`{"type":"object","additionalProperties":false,"required":["task_id"],"properties":{"task_id":{"type":"string"}}}`)),
	}, s.discardTaskHandler)
}

// Helper types for input deserialization.
type listProjectsInput struct{}
type getProjectInput struct {
	ProjectID string `json:"project_id"`
}
type listTasksInput struct {
	ProjectID string `json:"project_id,omitempty"`
	State     string `json:"state,omitempty"`
}
type getTaskInput struct {
	TaskID string `json:"task_id"`
}
type createTaskInput struct {
	ProjectID   string  `json:"project_id"`
	Title       string  `json:"title"`
	Description string  `json:"description,omitempty"`
	Template    *string `json:"template,omitempty"`
	Branch      *string `json:"branch,omitempty"`
}
type updateTaskInput struct {
	TaskID      string  `json:"task_id"`
	Title       *string `json:"title,omitempty"`
	Description *string `json:"description,omitempty"`
	State       *string `json:"state,omitempty"`
	Branch      *string `json:"branch,omitempty"`
}
type discardTaskInput struct {
	TaskID string `json:"task_id"`
}

// Helper types for output serialization (mirror Python exactly).
type mcpProject struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	Path string `json:"path"`
}

type mcpTask struct {
	ID                string  `json:"id"`
	ProjectID         string  `json:"project_id"`
	Title             string  `json:"title"`
	Description       string  `json:"description"`
	State             string  `json:"state"`
	Branch            *string `json:"branch"`
	Template          *string `json:"template"`
	PermissionProfile *string `json:"permission_profile"`
}

// errorResult wraps an error message with IsError=true.
func errorResult(msg string) *gosdk.CallToolResult {
	return &gosdk.CallToolResult{
		Content: []gosdk.Content{
			&gosdk.TextContent{Text: msg},
		},
		IsError: true,
	}
}

// okResult wraps a JSON string (already serialized) as success.
func okResult(jsonText string) *gosdk.CallToolResult {
	return &gosdk.CallToolResult{
		Content: []gosdk.Content{
			&gosdk.TextContent{Text: jsonText},
		},
		IsError: false,
	}
}

// projectShape converts a store.Project to mcpProject.
func projectShape(p *store.Project) mcpProject {
	return mcpProject{ID: p.ID, Name: p.Name, Path: p.Path}
}

// taskShape converts a store.Task to mcpTask, preserving null for nullable fields.
func taskShape(t *store.Task) mcpTask {
	return mcpTask{
		ID:                t.ID,
		ProjectID:         t.ProjectID,
		Title:             t.Title,
		Description:       t.Description,
		State:             t.State,
		Branch:            t.Branch,
		Template:          t.Template,
		PermissionProfile: t.PermissionProfile,
	}
}

// listProjectsHandler implements the list_projects tool.
func (s *Server) listProjectsHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	projects, err := s.projects.List(ctx)
	if err != nil {
		return errorResult(err.Error()), nil
	}

	out := make([]mcpProject, 0, len(projects))
	for _, p := range projects {
		out = append(out, projectShape(&p))
	}

	jsonBytes, _ := json.Marshal(out)
	return okResult(string(jsonBytes)), nil
}

// getProjectHandler implements the get_project tool.
func (s *Server) getProjectHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in getProjectInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	project, err := s.projects.Get(ctx, in.ProjectID)
	if err != nil {
		if errors.Is(err, store.ErrProjectNotFound) {
			return errorResult("project not found: " + in.ProjectID), nil
		}
		return errorResult(err.Error()), nil
	}

	jsonBytes, _ := json.Marshal(projectShape(project))
	return okResult(string(jsonBytes)), nil
}

// listTasksHandler implements the list_tasks tool.
func (s *Server) listTasksHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in listTasksInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	// Convert ProjectID to projectIDs slice if provided.
	var projectIDs []string
	if in.ProjectID != "" {
		projectIDs = []string{in.ProjectID}
	}

	tasks, err := s.tasks.List(ctx, projectIDs)
	if err != nil {
		return errorResult(err.Error()), nil
	}

	// Filter by state if provided (TasksService.List doesn't do this).
	if in.State != "" {
		filtered := make([]store.Task, 0, len(tasks))
		for _, t := range tasks {
			if t.State == in.State {
				filtered = append(filtered, t)
			}
		}
		tasks = filtered
	}

	out := make([]mcpTask, 0, len(tasks))
	for _, t := range tasks {
		out = append(out, taskShape(&t))
	}

	jsonBytes, _ := json.Marshal(out)
	return okResult(string(jsonBytes)), nil
}

// getTaskHandler implements the get_task tool.
func (s *Server) getTaskHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in getTaskInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	task, err := s.tasks.Get(ctx, in.TaskID)
	if err != nil {
		if errors.Is(err, store.ErrTaskNotFound) {
			return errorResult("task not found: " + in.TaskID), nil
		}
		return errorResult(err.Error()), nil
	}

	jsonBytes, _ := json.Marshal(taskShape(task))
	return okResult(string(jsonBytes)), nil
}

// createTaskHandler implements the create_task tool.
func (s *Server) createTaskHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in createTaskInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	task, err := s.tasks.Create(ctx, core.CreateTaskInput{
		ProjectID:   in.ProjectID,
		Title:       in.Title,
		Description: in.Description,
		Template:    in.Template,
		Branch:      in.Branch,
	})
	if err != nil {
		if errors.Is(err, catalog.ErrTemplateUnknown) {
			// Extract template name from error message if possible
			tmplName := ""
			if in.Template != nil {
				tmplName = *in.Template
			}
			return errorResult("unknown template: " + tmplName), nil
		}
		return errorResult(err.Error()), nil
	}

	jsonBytes, _ := json.Marshal(taskShape(task))
	return okResult(string(jsonBytes)), nil
}

// updateTaskHandler implements the update_task tool.
func (s *Server) updateTaskHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in updateTaskInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	task, err := s.tasks.Patch(ctx, in.TaskID, core.PatchTaskInput{
		Title:       in.Title,
		Description: in.Description,
		State:       in.State,
		Branch:      in.Branch,
	})
	if err != nil {
		if errors.Is(err, core.ErrInvalidTransition) {
			return errorResult("invalid state transition"), nil
		}
		if errors.Is(err, store.ErrTaskNotFound) {
			return errorResult("task not found: " + in.TaskID), nil
		}
		return errorResult(err.Error()), nil
	}

	jsonBytes, _ := json.Marshal(taskShape(task))
	return okResult(string(jsonBytes)), nil
}

// discardTaskHandler implements the discard_task tool.
func (s *Server) discardTaskHandler(ctx context.Context, req *gosdk.CallToolRequest) (*gosdk.CallToolResult, error) {
	var in discardTaskInput
	if err := json.Unmarshal(req.Params.Arguments, &in); err != nil {
		return errorResult(err.Error()), nil
	}

	task, err := s.tasks.Patch(ctx, in.TaskID, core.PatchTaskInput{
		State: ptrString("discarded"),
	})
	if err != nil {
		if errors.Is(err, core.ErrInvalidTransition) {
			return errorResult("invalid state transition"), nil
		}
		if errors.Is(err, store.ErrTaskNotFound) {
			return errorResult("task not found: " + in.TaskID), nil
		}
		return errorResult(err.Error()), nil
	}

	jsonBytes, _ := json.Marshal(taskShape(task))
	return okResult(string(jsonBytes)), nil
}

// ptrString is a helper to create a pointer to a string.
func ptrString(s string) *string {
	return &s
}
