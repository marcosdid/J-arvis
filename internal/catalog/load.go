package catalog

import (
	_ "embed"
	"fmt"
	"log"
	"regexp"
	"strings"

	"gopkg.in/yaml.v3"
)

//go:embed catalog.yml
var embeddedYAML []byte

var branchPrefixRe = regexp.MustCompile(`^[a-z][a-z0-9-]*/$`)

func MustLoad() *Catalog {
	c, err := Load(embeddedYAML)
	if err != nil {
		log.Fatalf("catalog: %v", err)
	}
	return c
}

func Load(raw []byte) (*Catalog, error) {
	var c Catalog
	if err := yaml.Unmarshal(raw, &c); err != nil {
		return nil, fmt.Errorf("%w: unmarshal: %v", ErrCatalog, err)
	}
	// Populate Name fields from map keys
	for k, v := range c.PermissionProfiles {
		v.Name = k
		c.PermissionProfiles[k] = v
	}
	for k, v := range c.Templates {
		v.Name = k
		c.Templates[k] = v
	}
	var problems []string
	if c.Version != "1" {
		problems = append(problems, fmt.Sprintf("unsupported version %q", c.Version))
	}
	if _, ok := c.PermissionProfiles[c.FallbackPermissionProfile]; !ok {
		problems = append(problems, fmt.Sprintf("fallback_permission_profile %q not in permission_profiles", c.FallbackPermissionProfile))
	}
	for name, t := range c.Templates {
		if _, ok := c.PermissionProfiles[t.DefaultPermissionProfile]; !ok {
			problems = append(problems, fmt.Sprintf("template %q references unknown profile %q", name, t.DefaultPermissionProfile))
		}
		if !branchPrefixRe.MatchString(t.BranchPrefix) {
			problems = append(problems, fmt.Sprintf("template %q: branch_prefix %q must match ^[a-z][a-z0-9-]*/$", name, t.BranchPrefix))
		}
	}
	if len(problems) > 0 {
		return nil, fmt.Errorf("%w: %s", ErrCatalog, strings.Join(problems, "; "))
	}
	return &c, nil
}
