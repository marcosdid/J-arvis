package catalog

import (
	_ "embed"
	"fmt"
	"log"

	"gopkg.in/yaml.v3"
)

//go:embed catalog.yml
var embeddedYAML []byte

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
	return &c, nil
}
