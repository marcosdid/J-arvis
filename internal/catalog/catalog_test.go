package catalog

import (
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
