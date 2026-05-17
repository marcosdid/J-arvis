package catalog

import (
	"errors"
	"strings"
	"testing"
)

func TestMustLoadEmbeddedSucceeds(t *testing.T) {
	c := MustLoad()
	if c.Version != "1" {
		t.Errorf("version=%q, want \"1\"", c.Version)
	}
	if c.FallbackPermissionProfile == "" {
		t.Error("fallback permission profile empty")
	}
	if _, ok := c.PermissionProfiles[c.FallbackPermissionProfile]; !ok {
		t.Errorf("fallback %q not in permission_profiles", c.FallbackPermissionProfile)
	}
	if len(c.Templates) == 0 {
		t.Error("templates empty")
	}
}

func TestLoadValidationCases(t *testing.T) {
	cases := []struct {
		name    string
		yaml    string
		wantErr string // substring of error message
	}{
		{
			name: "bad version",
			yaml: `version: "2"
fallback_permission_profile: x
permission_profiles: {x: {description: y, claude_args: []}}
templates: {}`,
			wantErr: `unsupported version "2"`,
		},
		{
			name: "fallback missing",
			yaml: `version: "1"
fallback_permission_profile: ghost
permission_profiles: {x: {description: y, claude_args: []}}
templates: {}`,
			wantErr: `fallback_permission_profile "ghost" not in permission_profiles`,
		},
		{
			name: "template references unknown profile",
			yaml: `version: "1"
fallback_permission_profile: x
permission_profiles: {x: {description: y, claude_args: []}}
templates:
  frontend: {description: f, default_permission_profile: ghost, branch_prefix: "feat/"}`,
			wantErr: `template "frontend" references unknown profile "ghost"`,
		},
		{
			name: "branch_prefix bad",
			yaml: `version: "1"
fallback_permission_profile: x
permission_profiles: {x: {description: y, claude_args: []}}
templates:
  bad: {description: f, default_permission_profile: x, branch_prefix: "Bad/"}`,
			wantErr: `branch_prefix "Bad/" must match`,
		},
		{
			name: "multiple errors aggregated",
			yaml: `version: "9"
fallback_permission_profile: ghost
permission_profiles: {}
templates: {}`,
			wantErr: `;`, // semicolon-separated aggregation
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := Load([]byte(tc.yaml))
			if err == nil {
				t.Fatalf("Load: nil error, want %q", tc.wantErr)
			}
			if !strings.Contains(err.Error(), tc.wantErr) {
				t.Errorf("err=%q, want substring %q", err.Error(), tc.wantErr)
			}
		})
	}
}

func TestResolveEmptyTemplateUsesFallback(t *testing.T) {
	c := MustLoad()
	r, err := c.Resolve("")
	if err != nil {
		t.Fatalf("Resolve(\"\"): %v", err)
	}
	if r.TemplateName != "" {
		t.Errorf("TemplateName=%q, want \"\"", r.TemplateName)
	}
	if r.ProfileName != c.FallbackPermissionProfile {
		t.Errorf("ProfileName=%q, want %q", r.ProfileName, c.FallbackPermissionProfile)
	}
}

func TestResolveKnownTemplateUsesItsProfile(t *testing.T) {
	c := MustLoad()
	// Pick any template that exists in the embedded catalog.
	var pickName string
	var pick Template
	for k, v := range c.Templates {
		pickName, pick = k, v
		break
	}
	r, err := c.Resolve(pickName)
	if err != nil {
		t.Fatalf("Resolve(%q): %v", pickName, err)
	}
	if r.TemplateName != pickName {
		t.Errorf("TemplateName=%q, want %q", r.TemplateName, pickName)
	}
	if r.ProfileName != pick.DefaultPermissionProfile {
		t.Errorf("ProfileName=%q, want %q", r.ProfileName, pick.DefaultPermissionProfile)
	}
	if r.BranchPrefix != pick.BranchPrefix {
		t.Errorf("BranchPrefix=%q, want %q", r.BranchPrefix, pick.BranchPrefix)
	}
}

func TestResolveUnknownTemplateErrors(t *testing.T) {
	c := MustLoad()
	_, err := c.Resolve("ghost-template")
	if !errors.Is(err, ErrTemplateUnknown) {
		t.Fatalf("err=%v, want ErrTemplateUnknown", err)
	}
}

func TestResolveProfileMissingErrors(t *testing.T) {
	c := MustLoad()
	_, err := c.ResolveProfile("ghost-profile")
	if !errors.Is(err, ErrProfileMissing) {
		t.Fatalf("err=%v, want ErrProfileMissing", err)
	}
}

func TestResolveProfileKnownReturnsClaudeArgs(t *testing.T) {
	c := MustLoad()
	p, err := c.ResolveProfile(c.FallbackPermissionProfile)
	if err != nil {
		t.Fatalf("ResolveProfile: %v", err)
	}
	if p.Name != c.FallbackPermissionProfile {
		t.Errorf("Name=%q, want %q", p.Name, c.FallbackPermissionProfile)
	}
	// ClaudeArgs may be empty (default profile) — just verify it's not nil.
	if p.ClaudeArgs == nil {
		t.Error("ClaudeArgs is nil; want []string (possibly empty)")
	}
}
