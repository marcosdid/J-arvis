package core

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
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

func TestManifestValidateCases(t *testing.T) {
	cases := []struct {
		name    string
		yaml    string
		wantErr string
	}{
		{
			name: "bad version",
			yaml: `version: "2"
services: {db: {image: x, port: 1}}`,
			wantErr: `unsupported version "2"`,
		},
		{
			name: "image and build",
			yaml: `version: "1"
services: {db: {image: x, build: ./y, port: 1}}`,
			wantErr: `service "db": image and build are mutually exclusive`,
		},
		{
			name: "no image no build",
			yaml: `version: "1"
services: {db: {port: 1}}`,
			wantErr: `service "db": must specify image or build`,
		},
		{
			name: "depends_on unknown",
			yaml: `version: "1"
services:
  a: {image: x, port: 1, depends_on: [ghost]}`,
			wantErr: `service "a": depends_on "ghost" not found`,
		},
		{
			name: "cycle in depends_on",
			yaml: `version: "1"
services:
  a: {image: x, depends_on: [b]}
  b: {image: y, depends_on: [a]}`,
			wantErr: `circular`,
		},
		{
			name: "token references service without port",
			yaml: `version: "1"
services:
  a: {image: x}
  b: {image: y, env: {URL_A: "$URL_a"}}`,
			wantErr: `service "b": env value "$URL_a" references service "a" which has no port`,
		},
		{
			name: "token references unknown service",
			yaml: `version: "1"
services:
  a: {image: x, env: {URL_GHOST: "$URL_ghost"}}`,
			wantErr: `service "a": env value "$URL_ghost" references unknown service "ghost"`,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var m ManifestSpec
			if err := yaml.Unmarshal([]byte(tc.yaml), &m); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			err := m.Validate()
			if err == nil {
				t.Fatalf("Validate: nil err, want substring %q", tc.wantErr)
			}
			if !strings.Contains(err.Error(), tc.wantErr) {
				t.Errorf("err=%q, want substring %q", err.Error(), tc.wantErr)
			}
		})
	}
}

func TestResolveSubstitutions(t *testing.T) {
	env := map[string]string{
		"DATABASE_URL": "postgresql://localhost:$PORT_db/postgres",
		"VITE_API":     "$URL_backend",
		"RUN_LABEL":    "run-$RUN_ID",
		"WORKDIR":      "$CWD",
		"PLAIN":        "no substitution",
	}
	ports := map[string]int{"db": 31000, "backend": 31001}
	out := ResolveSubstitutions(env, ports, "abc-123", "/tmp/wt")

	if out["DATABASE_URL"] != "postgresql://localhost:31000/postgres" {
		t.Errorf("DATABASE_URL=%q", out["DATABASE_URL"])
	}
	if out["VITE_API"] != "http://localhost:31001" {
		t.Errorf("VITE_API=%q", out["VITE_API"])
	}
	if out["RUN_LABEL"] != "run-abc-123" {
		t.Errorf("RUN_LABEL=%q", out["RUN_LABEL"])
	}
	if out["WORKDIR"] != "/tmp/wt" {
		t.Errorf("WORKDIR=%q", out["WORKDIR"])
	}
	if out["PLAIN"] != "no substitution" {
		t.Errorf("PLAIN modified")
	}
}
