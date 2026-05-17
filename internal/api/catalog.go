package api

import (
	"sort"

	"github.com/marcosdid/jarvis/internal/catalog"
)

type CatalogAPI struct{ root *catalog.Catalog }

func NewCatalogAPI(root *catalog.Catalog) *CatalogAPI {
	return &CatalogAPI{root: root}
}

type CatalogView struct {
	Version                   string                      `json:"version"`
	FallbackPermissionProfile string                      `json:"fallback_permission_profile"`
	PermissionProfiles        []catalog.PermissionProfile `json:"permission_profiles"`
	Templates                 []catalog.Template          `json:"templates"`
}

func (a *CatalogAPI) Get() CatalogView {
	profs := make([]catalog.PermissionProfile, 0, len(a.root.PermissionProfiles))
	for _, p := range a.root.PermissionProfiles {
		profs = append(profs, p)
	}
	sort.Slice(profs, func(i, j int) bool { return profs[i].Name < profs[j].Name })

	tmpls := make([]catalog.Template, 0, len(a.root.Templates))
	for _, t := range a.root.Templates {
		tmpls = append(tmpls, t)
	}
	sort.Slice(tmpls, func(i, j int) bool { return tmpls[i].Name < tmpls[j].Name })

	return CatalogView{
		Version:                   a.root.Version,
		FallbackPermissionProfile: a.root.FallbackPermissionProfile,
		PermissionProfiles:        profs,
		Templates:                 tmpls,
	}
}
