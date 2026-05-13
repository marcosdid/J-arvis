package sandbox

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSandboxAvailable_Ok(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"ai-jail", "gnome-terminal"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("#!/bin/sh\n"), 0o755); err != nil {
			t.Fatalf("write %s: %v", name, err)
		}
	}
	t.Setenv("PATH", dir)
	t.Setenv("JARVIS_TERMINAL", "")
	if err := SandboxAvailable(); err != nil {
		t.Errorf("SandboxAvailable: got %v, want nil", err)
	}
}

func TestSandboxAvailable_MissingAijail(t *testing.T) {
	dir := t.TempDir()
	_ = os.WriteFile(filepath.Join(dir, "gnome-terminal"), []byte("#!/bin/sh\n"), 0o755)
	t.Setenv("PATH", dir)
	t.Setenv("JARVIS_TERMINAL", "")
	err := SandboxAvailable()
	if err == nil || !strings.Contains(err.Error(), "ai-jail") {
		t.Errorf("expected ai-jail-missing error, got %v", err)
	}
}

func TestSandboxAvailable_MissingTerminal(t *testing.T) {
	dir := t.TempDir()
	_ = os.WriteFile(filepath.Join(dir, "ai-jail"), []byte("#!/bin/sh\n"), 0o755)
	t.Setenv("PATH", dir)
	t.Setenv("JARVIS_TERMINAL", "")
	err := SandboxAvailable()
	if err == nil || !strings.Contains(err.Error(), "terminal") {
		t.Errorf("expected terminal-missing error, got %v", err)
	}
}

func TestDiagnoseSandbox_HumanReadable(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	t.Setenv("JARVIS_TERMINAL", "")
	got := DiagnoseSandbox()
	if got == "" {
		t.Error("expected non-empty diagnosis when sandbox unavailable")
	}
}
