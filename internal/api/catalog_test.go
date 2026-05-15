package api

import (
	"sort"
	"testing"

	"github.com/marcosdid/jarvis/internal/catalog"
)

func TestCatalogAPIGetReturnsSortedView(t *testing.T) {
	root := catalog.MustLoad()
	a := NewCatalogAPI(root)
	v := a.Get()
	if v.Version != "1" {
		t.Errorf("Version=%q, want \"1\"", v.Version)
	}
	if v.FallbackPermissionProfile != root.FallbackPermissionProfile {
		t.Errorf("Fallback=%q, want %q", v.FallbackPermissionProfile, root.FallbackPermissionProfile)
	}
	if len(v.PermissionProfiles) != len(root.PermissionProfiles) {
		t.Errorf("profiles len=%d, want %d", len(v.PermissionProfiles), len(root.PermissionProfiles))
	}
	if len(v.Templates) != len(root.Templates) {
		t.Errorf("templates len=%d, want %d", len(v.Templates), len(root.Templates))
	}
	// Both lists must be sorted by Name (deterministic UI ordering).
	if !sort.SliceIsSorted(v.PermissionProfiles, func(i, j int) bool {
		return v.PermissionProfiles[i].Name < v.PermissionProfiles[j].Name
	}) {
		t.Error("permission profiles not sorted by Name")
	}
	if !sort.SliceIsSorted(v.Templates, func(i, j int) bool {
		return v.Templates[i].Name < v.Templates[j].Name
	}) {
		t.Error("templates not sorted by Name")
	}
}
