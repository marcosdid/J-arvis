package sandbox

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestFindTranscriptFiles_OrderedByMtime(t *testing.T) {
	dir := t.TempDir()
	first := filepath.Join(dir, "aaa.jsonl")
	second := filepath.Join(dir, "bbb.jsonl")
	if err := os.WriteFile(first, []byte("{}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	past := time.Now().Add(-2 * time.Hour)
	_ = os.Chtimes(first, past, past)
	if err := os.WriteFile(second, []byte("{}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := FindTranscriptFiles(dir)
	if err != nil {
		t.Fatalf("FindTranscriptFiles: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("want 2, got %d", len(got))
	}
	if got[0] != first || got[1] != second {
		t.Errorf("ordering: got %v, want [%s, %s]", got, first, second)
	}
}

func TestFindTranscriptFiles_MissingDirReturnsEmpty(t *testing.T) {
	got, err := FindTranscriptFiles(filepath.Join(t.TempDir(), "does-not-exist"))
	if err != nil {
		t.Errorf("want nil err, got %v", err)
	}
	if len(got) != 0 {
		t.Errorf("want empty, got %v", got)
	}
}

func TestFindTranscriptFiles_IgnoresNonJsonl(t *testing.T) {
	dir := t.TempDir()
	_ = os.WriteFile(filepath.Join(dir, "x.jsonl"), []byte("{}\n"), 0o644)
	_ = os.WriteFile(filepath.Join(dir, "y.txt"), []byte("noise"), 0o644)
	got, _ := FindTranscriptFiles(dir)
	if len(got) != 1 {
		t.Errorf("want 1, got %v", got)
	}
}

func TestParseTranscript_UserAssistant(t *testing.T) {
	msgs, err := ParseTranscript("testdata/transcripts/sample-user-assistant.jsonl")
	if err != nil {
		t.Fatalf("ParseTranscript: %v", err)
	}
	if len(msgs) != 2 {
		t.Fatalf("want 2, got %d: %+v", len(msgs), msgs)
	}
	if msgs[0].Role != "user" || msgs[0].Content != "oi" {
		t.Errorf("msg[0]: %+v", msgs[0])
	}
	if msgs[1].Role != "assistant" || msgs[1].Content != "oi de volta" {
		t.Errorf("msg[1]: %+v", msgs[1])
	}
}

func TestParseTranscript_ToolUseFansOut(t *testing.T) {
	msgs, err := ParseTranscript("testdata/transcripts/sample-tool-use.jsonl")
	if err != nil {
		t.Fatalf("ParseTranscript: %v", err)
	}
	if len(msgs) != 4 {
		t.Fatalf("want 4 msgs, got %d: %+v", len(msgs), msgs)
	}
	var hasToolUse, hasToolResult bool
	for _, m := range msgs {
		if m.Role == "tool_use" {
			hasToolUse = true
			if m.ToolName == nil || *m.ToolName != "Read" {
				t.Errorf("tool_use ToolName: got %v, want Read", m.ToolName)
			}
		}
		if m.Role == "tool_result" {
			hasToolResult = true
		}
	}
	if !hasToolUse {
		t.Error("missing tool_use message")
	}
	if !hasToolResult {
		t.Error("missing tool_result message")
	}
}

func TestParseTranscript_SkipsMalformedAndUnknown(t *testing.T) {
	msgs, err := ParseTranscript("testdata/transcripts/sample-malformed.jsonl")
	if err != nil {
		t.Fatalf("ParseTranscript: %v", err)
	}
	if len(msgs) != 1 {
		t.Errorf("want 1 valid msg, got %d: %+v", len(msgs), msgs)
	}
	if msgs[0].Role != "user" {
		t.Errorf("msg[0].Role: %q", msgs[0].Role)
	}
}
