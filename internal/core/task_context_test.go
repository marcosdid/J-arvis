package core

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/marcosdid/jarvis/internal/store"
)

func ptrStr(s string) *string { return &s }

func TestWriteTaskContext_WritesMarkdownWithStructure(t *testing.T) {
	tmp := t.TempDir()
	tmpl := "backend"
	in := TaskContextInput{
		Cwd:     tmp,
		Project: store.Project{Name: "gcb-hub", Path: "/orig/gcb-hub"},
		Task: store.Task{
			ID:       "t1",
			Title:    "Validar quality gates frontend+backend",
			Template: &tmpl,
			State:    "in_progress",
		},
		Branch: "feat/validate-qg",
		Repos: []store.Repository{
			{Name: "gcb-hub", SubPath: "."},
			{Name: "backend", SubPath: "backend"},
			{Name: "frontend", SubPath: "frontend"},
		},
	}
	if err := WriteTaskContext(in); err != nil {
		t.Fatalf("WriteTaskContext: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(tmp, ".jarvis", "CONTEXT.md"))
	if err != nil {
		t.Fatalf("read .jarvis/CONTEXT.md: %v", err)
	}
	s := string(data)
	wants := []string{
		"gcb-hub", "backend/", "frontend/",
		"feat/validate-qg",
		"Validar quality gates frontend+backend",
		"backend", // template
	}
	for _, w := range wants {
		if !strings.Contains(s, w) {
			t.Errorf("CONTEXT.md missing %q. Content:\n%s", w, s)
		}
	}
}

func TestWriteTaskContext_CreatesJarvisDirIfMissing(t *testing.T) {
	tmp := t.TempDir()
	in := TaskContextInput{
		Cwd:     tmp,
		Project: store.Project{Name: "p", Path: "/p"},
		Task:    store.Task{ID: "t", Title: "x", State: "ready"},
		Branch:  "b",
		Repos:   []store.Repository{{Name: "p", SubPath: "."}},
	}
	if err := WriteTaskContext(in); err != nil {
		t.Fatalf("WriteTaskContext: %v", err)
	}
	info, err := os.Stat(filepath.Join(tmp, ".jarvis"))
	if err != nil {
		t.Errorf(".jarvis dir not created: %v", err)
	} else if !info.IsDir() {
		t.Error(".jarvis is not a directory")
	}
}

func TestWriteTaskContext_OmitsTemplateWhenNil(t *testing.T) {
	tmp := t.TempDir()
	in := TaskContextInput{
		Cwd:     tmp,
		Project: store.Project{Name: "p", Path: "/p"},
		Task:    store.Task{ID: "t", Title: "no template task", Template: nil, State: "ready"},
		Branch:  "b",
		Repos:   []store.Repository{{Name: "p", SubPath: "."}},
	}
	if err := WriteTaskContext(in); err != nil {
		t.Fatalf("WriteTaskContext: %v", err)
	}
	data, _ := os.ReadFile(filepath.Join(tmp, ".jarvis", "CONTEXT.md"))
	if strings.Contains(string(data), "Template:") {
		t.Errorf("Template line should not appear when nil:\n%s", string(data))
	}
}
