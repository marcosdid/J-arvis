package core

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"gopkg.in/yaml.v3"
)

var (
	ErrManifestMissing = errors.New("runs: manifest .orchestrator/run.yml missing")
	ErrManifestInvalid = errors.New("runs: manifest invalid")
)

type HealthcheckSpec struct {
	Test     []string      `yaml:"test"     json:"test"`
	Interval time.Duration `yaml:"interval" json:"interval"`
	Timeout  time.Duration `yaml:"timeout"  json:"timeout"`
	Retries  int           `yaml:"retries"  json:"retries"`
}

type SeedSpec struct {
	Command []string      `yaml:"command" json:"command"`
	Timeout time.Duration `yaml:"timeout" json:"timeout"`
}

type ServiceSpec struct {
	Image       string            `yaml:"image,omitempty"        json:"image,omitempty"`
	Build       string            `yaml:"build,omitempty"        json:"build,omitempty"`
	Port        int               `yaml:"port,omitempty"         json:"port,omitempty"`
	DependsOn   []string          `yaml:"depends_on,omitempty"   json:"depends_on,omitempty"`
	Env         map[string]string `yaml:"env,omitempty"          json:"env,omitempty"`
	Healthcheck *HealthcheckSpec  `yaml:"healthcheck,omitempty"  json:"healthcheck,omitempty"`
	Seed        *SeedSpec         `yaml:"seed,omitempty"         json:"seed,omitempty"`
	MountSource *bool             `yaml:"mount_source,omitempty" json:"mount_source,omitempty"`
}

type ManifestSpec struct {
	Version  string                 `yaml:"version"  json:"version"`
	Services map[string]ServiceSpec `yaml:"services" json:"services"`
}

func LoadManifest(cwd string) (*ManifestSpec, error) {
	path := filepath.Join(cwd, ".orchestrator", "run.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, ErrManifestMissing
		}
		return nil, fmt.Errorf("%w: read: %v", ErrManifestInvalid, err)
	}
	var m ManifestSpec
	if err := yaml.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("%w: unmarshal: %v", ErrManifestInvalid, err)
	}
	return &m, nil
}
