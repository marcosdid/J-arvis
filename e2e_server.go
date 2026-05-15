//go:build !e2e_http

package main

import (
	"github.com/marcosdid/jarvis/internal/api"
)

// startE2EServer is a no-op in normal builds. Replaced by the e2e_http
// build with a real HTTP server exposing /e2e/* endpoints.
func startE2EServer(_ *api.TasksAPI, _ *api.ProjectsAPI, _ *api.WorktreesAPI, _ *api.SessionsAPI, _ *api.MasterAPI) {
}
