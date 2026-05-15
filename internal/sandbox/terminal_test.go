package sandbox

import (
	"os"
	"path/filepath"
	"testing"
)

// withFakeBin creates dir + an executable file, returns dir for $PATH injection.
func withFakeBin(t *testing.T, name string) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte("#!/bin/sh\nexit 0\n"), 0o755); err != nil {
		t.Fatalf("write fake bin: %v", err)
	}
	return dir
}

func TestDetectTerminal_HonorsJarvisOverride(t *testing.T) {
	dir := withFakeBin(t, "kitty")
	t.Setenv("PATH", dir)
	t.Setenv("JARVIS_TERMINAL", "kitty")
	got, err := DetectTerminal()
	if err != nil {
		t.Fatalf("DetectTerminal: %v", err)
	}
	if got != "kitty" {
		t.Errorf("got %q, want kitty", got)
	}
}

func TestDetectTerminal_RejectsUnknownOverride(t *testing.T) {
	t.Setenv("JARVIS_TERMINAL", "totally-not-a-terminal")
	_, err := DetectTerminal()
	if err == nil {
		t.Error("expected error for unknown override")
	}
}

func TestDetectTerminal_ScansPathInPriority(t *testing.T) {
	dir1 := withFakeBin(t, "xterm")
	dir2 := withFakeBin(t, "gnome-terminal")
	t.Setenv("PATH", dir1+":"+dir2)
	t.Setenv("JARVIS_TERMINAL", "")
	got, err := DetectTerminal()
	if err != nil {
		t.Fatalf("DetectTerminal: %v", err)
	}
	if got != "gnome-terminal" {
		t.Errorf("got %q, want gnome-terminal (higher priority)", got)
	}
}

func TestDetectTerminal_NoneFound(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	t.Setenv("JARVIS_TERMINAL", "")
	_, err := DetectTerminal()
	if err == nil {
		t.Error("expected ErrNoTerminal")
	}
}

func TestBuildTerminalCommand_GnomeTerminal(t *testing.T) {
	got := BuildTerminalCommand("gnome-terminal", []string{"ai-jail"})
	want := []string{"gnome-terminal", "--", "ai-jail"}
	if !equalSlice(got, want) {
		t.Errorf("got %v, want %v", got, want)
	}
}

func TestBuildTerminalCommand_Kitty(t *testing.T) {
	got := BuildTerminalCommand("kitty", []string{"ai-jail"})
	want := []string{"kitty", "ai-jail"}
	if !equalSlice(got, want) {
		t.Errorf("got %v, want %v", got, want)
	}
}

func equalSlice(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
