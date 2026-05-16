package core

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadManifest_NotFound_ReturnsErrManifestMissing(t *testing.T) {
	_, err := LoadManifest(t.TempDir())
	if !errors.Is(err, ErrManifestMissing) {
		t.Errorf("err=%v, want ErrManifestMissing", err)
	}
}

func TestLoadManifest_Valid_ReturnsSpec(t *testing.T) {
	dir := t.TempDir()
	orcDir := filepath.Join(dir, ".orchestrator")
	_ = os.MkdirAll(orcDir, 0o755)
	yaml := `version: "1"
services:
  db:
    image: postgres:15
    port: 5432
`
	if err := os.WriteFile(filepath.Join(orcDir, "run.yml"), []byte(yaml), 0o644); err != nil {
		t.Fatal(err)
	}
	m, err := LoadManifest(dir)
	if err != nil {
		t.Fatalf("LoadManifest: %v", err)
	}
	if m.Version != "1" {
		t.Errorf("Version=%q, want \"1\"", m.Version)
	}
	if _, ok := m.Services["db"]; !ok {
		t.Error("db service missing")
	}
	if m.Services["db"].Port != 5432 {
		t.Errorf("db.Port=%d, want 5432", m.Services["db"].Port)
	}
}
