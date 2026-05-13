package sandbox

import (
	"bufio"
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// TranscriptMessage is one renderable message extracted from claude's JSONL.
type TranscriptMessage struct {
	Role       string    `json:"role"`
	Content    string    `json:"content"`
	ToolName   *string   `json:"tool_name"`
	Timestamp  time.Time `json:"timestamp"`
	SourceFile string    `json:"source_file"`
}

// FindTranscriptFiles returns absolute paths of all .jsonl files in dir,
// ordered by file mtime ASC. Missing dir → nil, nil (graceful).
func FindTranscriptFiles(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	type entry struct {
		path  string
		mtime time.Time
	}
	var list []entry
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".jsonl") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		list = append(list, entry{
			path:  filepath.Join(dir, e.Name()),
			mtime: info.ModTime(),
		})
	}
	sort.Slice(list, func(i, j int) bool { return list[i].mtime.Before(list[j].mtime) })
	out := make([]string, len(list))
	for i, e := range list {
		out[i] = e.path
	}
	return out, nil
}

type rawEntry struct {
	Type      string          `json:"type"`
	Message   json.RawMessage `json:"message"`
	Content   json.RawMessage `json:"content"`
	Timestamp time.Time       `json:"timestamp"`
}

// ParseTranscript reads one JSONL file. Malformed lines and unknown types are
// skipped + logged. Returns ordered TranscriptMessages.
func ParseTranscript(path string) ([]TranscriptMessage, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = f.Close() }()
	source := filepath.Base(path)

	var out []TranscriptMessage
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 64*1024), 8*1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var raw rawEntry
		if err := json.Unmarshal([]byte(line), &raw); err != nil {
			log.Printf("transcript parse: skip malformed line in %s: %v", source, err)
			continue
		}
		msgs := mapEntry(raw, source)
		out = append(out, msgs...)
	}
	if err := scanner.Err(); err != nil {
		return out, err
	}
	return out, nil
}

func mapEntry(raw rawEntry, source string) []TranscriptMessage {
	switch raw.Type {
	case "user":
		text := extractUserText(raw.Message)
		return []TranscriptMessage{{
			Role: "user", Content: text, Timestamp: raw.Timestamp, SourceFile: source,
		}}
	case "assistant":
		return mapAssistantBlocks(raw.Message, raw.Timestamp, source)
	case "tool_result":
		return []TranscriptMessage{{
			Role: "tool_result", Content: rawString(raw.Content),
			Timestamp: raw.Timestamp, SourceFile: source,
		}}
	default:
		log.Printf("transcript parse: skip unknown type %q in %s", raw.Type, source)
		return nil
	}
}

func extractUserText(msg json.RawMessage) string {
	var v struct {
		Content json.RawMessage `json:"content"`
	}
	if err := json.Unmarshal(msg, &v); err != nil {
		return ""
	}
	return rawString(v.Content)
}

func rawString(r json.RawMessage) string {
	if len(r) == 0 {
		return ""
	}
	var s string
	if err := json.Unmarshal(r, &s); err == nil {
		return s
	}
	return string(r)
}

func mapAssistantBlocks(msg json.RawMessage, ts time.Time, source string) []TranscriptMessage {
	var wrap struct {
		Content []struct {
			Type  string          `json:"type"`
			Text  string          `json:"text"`
			Name  string          `json:"name"`
			Input json.RawMessage `json:"input"`
		} `json:"content"`
	}
	if err := json.Unmarshal(msg, &wrap); err != nil {
		var v struct {
			Content string `json:"content"`
		}
		if err2 := json.Unmarshal(msg, &v); err2 == nil && v.Content != "" {
			return []TranscriptMessage{{
				Role: "assistant", Content: v.Content, Timestamp: ts, SourceFile: source,
			}}
		}
		return nil
	}
	var out []TranscriptMessage
	for _, b := range wrap.Content {
		switch b.Type {
		case "text":
			out = append(out, TranscriptMessage{
				Role: "assistant", Content: b.Text, Timestamp: ts, SourceFile: source,
			})
		case "tool_use":
			name := b.Name
			out = append(out, TranscriptMessage{
				Role: "tool_use", Content: rawString(b.Input),
				ToolName: &name, Timestamp: ts, SourceFile: source,
			})
		}
	}
	return out
}
