// Package catalog holds the embedded YAML config that defines templates
// (task presets) and permission profiles (claude CLI-flag presets). The
// YAML is shipped inside the binary via //go:embed and validated once at
// boot — invalid catalog = process refuses to start.
package catalog

import (
	"errors"
	"fmt"
)

var (
	ErrCatalog         = errors.New("catalog")
	ErrTemplateUnknown = fmt.Errorf("%w: template unknown", ErrCatalog)
	ErrProfileMissing  = fmt.Errorf("%w: permission profile missing", ErrCatalog)
)

type PermissionProfile struct {
	Name        string   `yaml:"-"           json:"name"`
	Description string   `yaml:"description" json:"description"`
	ClaudeArgs  []string `yaml:"claude_args" json:"claude_args"`
}

type Template struct {
	Name                     string `yaml:"-"                          json:"name"`
	Description              string `yaml:"description"                 json:"description"`
	DefaultPermissionProfile string `yaml:"default_permission_profile"  json:"default_permission_profile"`
	BranchPrefix             string `yaml:"branch_prefix"               json:"branch_prefix"`
}

type Catalog struct {
	Version                   string                       `yaml:"version"                      json:"version"`
	FallbackPermissionProfile string                       `yaml:"fallback_permission_profile"  json:"fallback_permission_profile"`
	PermissionProfiles        map[string]PermissionProfile `yaml:"permission_profiles"          json:"-"`
	Templates                 map[string]Template          `yaml:"templates"                    json:"-"`
}

type Resolved struct {
	TemplateName string
	ProfileName  string
	ClaudeArgs   []string
	BranchPrefix string
}

func (c *Catalog) Resolve(templateName string) (Resolved, error) {
	if templateName == "" {
		p := c.PermissionProfiles[c.FallbackPermissionProfile]
		return Resolved{
			ProfileName: c.FallbackPermissionProfile,
			ClaudeArgs:  p.ClaudeArgs,
		}, nil
	}
	t, ok := c.Templates[templateName]
	if !ok {
		return Resolved{}, fmt.Errorf("%w: %s", ErrTemplateUnknown, templateName)
	}
	p := c.PermissionProfiles[t.DefaultPermissionProfile]
	return Resolved{
		TemplateName: templateName,
		ProfileName:  t.DefaultPermissionProfile,
		ClaudeArgs:   p.ClaudeArgs,
		BranchPrefix: t.BranchPrefix,
	}, nil
}

func (c *Catalog) ResolveProfile(profileName string) (PermissionProfile, error) {
	p, ok := c.PermissionProfiles[profileName]
	if !ok {
		return PermissionProfile{}, fmt.Errorf("%w: %s", ErrProfileMissing, profileName)
	}
	return p, nil
}
