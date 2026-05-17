package core

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
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

var tokenRe = regexp.MustCompile(`\$(?:PORT|URL)_([A-Za-z0-9_-]+)`)

func (m *ManifestSpec) Validate() error {
	var problems []string

	if m.Version != "1" {
		problems = append(problems, fmt.Sprintf("unsupported version %q", m.Version))
	}

	names := make([]string, 0, len(m.Services))
	for name := range m.Services {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		spec := m.Services[name]
		hasImage := spec.Image != ""
		hasBuild := spec.Build != ""
		switch {
		case hasImage && hasBuild:
			problems = append(problems, fmt.Sprintf("service %q: image and build are mutually exclusive", name))
		case !hasImage && !hasBuild:
			problems = append(problems, fmt.Sprintf("service %q: must specify image or build", name))
		}
		for _, dep := range spec.DependsOn {
			if _, ok := m.Services[dep]; !ok {
				problems = append(problems, fmt.Sprintf("service %q: depends_on %q not found", name, dep))
			}
		}
		for _, envVal := range spec.Env {
			for _, match := range tokenRe.FindAllStringSubmatch(envVal, -1) {
				refSvc := match[1]
				ref, ok := m.Services[refSvc]
				if !ok {
					problems = append(problems, fmt.Sprintf(
						"service %q: env value %q references unknown service %q",
						name, envVal, refSvc))
					continue
				}
				if ref.Port == 0 {
					problems = append(problems, fmt.Sprintf(
						"service %q: env value %q references service %q which has no port",
						name, envVal, refSvc))
				}
			}
		}
	}

	if cycleErr := detectCycle(m.Services); cycleErr != "" {
		problems = append(problems, cycleErr)
	}

	if len(problems) > 0 {
		return fmt.Errorf("%w: %s", ErrManifestInvalid, strings.Join(problems, "; "))
	}
	return nil
}

func detectCycle(services map[string]ServiceSpec) string {
	const (
		white = 0
		gray  = 1
		black = 2
	)
	color := map[string]int{}
	for name := range services {
		color[name] = white
	}
	var visit func(name string, path []string) string
	visit = func(name string, path []string) string {
		color[name] = gray
		for _, dep := range services[name].DependsOn {
			switch color[dep] {
			case gray:
				return fmt.Sprintf("circular depends_on: %s -> %s", strings.Join(append(path, name), " -> "), dep)
			case white:
				if cyc := visit(dep, append(path, name)); cyc != "" {
					return cyc
				}
			}
		}
		color[name] = black
		return ""
	}
	names := make([]string, 0, len(services))
	for name := range services {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		if color[name] == white {
			if cyc := visit(name, nil); cyc != "" {
				return cyc
			}
		}
	}
	return ""
}

func ResolveSubstitutions(env map[string]string, ports map[string]int, runID, cwd string) map[string]string {
	out := make(map[string]string, len(env))
	for k, v := range env {
		v = strings.ReplaceAll(v, "$RUN_ID", runID)
		v = strings.ReplaceAll(v, "$CWD", cwd)
		v = tokenRe.ReplaceAllStringFunc(v, func(match string) string {
			groups := tokenRe.FindStringSubmatch(match)
			svc := groups[1]
			port := ports[svc]
			if strings.HasPrefix(match, "$URL_") {
				return fmt.Sprintf("http://localhost:%d", port)
			}
			return fmt.Sprintf("%d", port)
		})
		out[k] = v
	}
	return out
}
