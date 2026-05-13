//go:build e2e_http

package main

import (
	"log"

	"github.com/marcosdid/jarvis/internal/api"
)

func startE2EServer(tasks *api.TasksAPI, projects *api.ProjectsAPI, worktrees *api.WorktreesAPI, master *api.MasterAPI) {
	srv := api.NewE2EServer(tasks, projects, worktrees, master)
	if _, err := srv.Start(); err != nil {
		log.Fatalf("e2e server: %v", err)
	}
}
