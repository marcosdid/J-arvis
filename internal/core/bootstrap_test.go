package core

import (
	"strings"
	"testing"
)

func TestBootstrapPromptEmbedded(t *testing.T) {
	if len(bootstrapPromptTemplate) < 500 {
		t.Fatalf("bootstrap prompt seems empty or truncated: %d bytes", len(bootstrapPromptTemplate))
	}
	if !strings.Contains(bootstrapPromptTemplate, "version: \"1\"") {
		t.Error("prompt missing version: \"1\" example")
	}
	if !strings.Contains(bootstrapPromptTemplate, ".orchestrator/run.yml") {
		t.Error("prompt missing target path reference")
	}
}
