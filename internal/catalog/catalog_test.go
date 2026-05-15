package catalog

import "testing"

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
