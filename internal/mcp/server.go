package mcp

import (
	"net/http"

	gosdk "github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
)

// Server wraps the SDK *mcp.Server with J-arvis-specific dependencies
// (TasksService, ProjectsService, Catalog) and a single boot-generated
// bearer token. Spec #2 reads token.Value() to write into the master
// session's .claude/settings.json.
type Server struct {
	tasks    *core.TasksService
	projects *core.ProjectsService
	catalog  *catalog.Catalog
	token    *BearerToken
	mcp      *gosdk.Server
}

func NewServer(
	tasks *core.TasksService,
	projects *core.ProjectsService,
	cat *catalog.Catalog,
	tok *BearerToken,
) *Server {
	mcpSrv := gosdk.NewServer(&gosdk.Implementation{
		Name:    "j-arvis-master",
		Version: "0.1.0",
	}, nil)
	s := &Server{tasks: tasks, projects: projects, catalog: cat, token: tok, mcp: mcpSrv}
	s.registerTools()
	return s
}

// Token exposes the bearer token so main.go can pass it to spec-#2 wiring
// (settings.json writer). NOT for logging.
func (s *Server) Token() *BearerToken { return s.token }

// Handler returns the auth-protected http.Handler to mount at /api/mcp on
// the shared internal listener (localhttp.Server).
func (s *Server) Handler() http.Handler {
	sdkHandler := gosdk.NewStreamableHTTPHandler(
		func(*http.Request) *gosdk.Server { return s.mcp },
		nil,
	)
	return authMiddleware(s.token, sdkHandler)
}
