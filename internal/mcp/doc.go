// Package mcp wraps github.com/modelcontextprotocol/go-sdk for J-arvis. It
// exposes 7 task/project tools to the master-Claude session over JSON-RPC,
// mounted at /api/mcp on the shared internal listener (internal/localhttp).
//
// SDK API signatures verified against v1.5.0 (released 2026-04-07) via
// `go doc github.com/modelcontextprotocol/go-sdk/mcp.*`. Keep this comment in
// sync if the SDK is bumped — the rest of the package treats these as ground
// truth:
//
//	NewServer(impl *Implementation, options *ServerOptions) *Server
//	AddTool[In, Out any](s *Server, t *Tool, h ToolHandlerFor[In, Out])
//	type ToolHandlerFor[In, Out any] func(
//	    ctx context.Context, req *CallToolRequest, in In,
//	) (*CallToolResult, Out, error)
//	NewStreamableHTTPHandler(
//	    getServer func(*http.Request) *Server,
//	    opts *StreamableHTTPOptions,
//	) *StreamableHTTPHandler
//	type Implementation struct{ Name, Title, Version string }
//	type CallToolResult struct{ Content []Content; IsError bool; ... }
//
// Authentication is a single boot-generated bearer token validated by
// authMiddleware in auth.go (constant-time compare, crypto/rand 256-bit).
// Spec #2 (master session upgrade) reads BearerToken.Value() and writes it
// into .claude/settings.json so master-claude can call the tools.
package mcp
