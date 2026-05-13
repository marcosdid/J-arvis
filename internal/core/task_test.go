package core

import "testing"

func TestIsValidTransition(t *testing.T) {
	tests := []struct {
		from, to string
		ok       bool
	}{
		{"idea", "ready", true},
		{"idea", "discarded", true},
		{"ready", "in_progress", true},
		{"in_progress", "review", true},
		{"review", "done", true},
		{"done", "discarded", true},
		{"in_progress", "ready", true},
		{"done", "in_progress", false},
		{"discarded", "idea", false},
		{"idea", "done", false},
	}
	for _, tc := range tests {
		t.Run(tc.from+"->"+tc.to, func(t *testing.T) {
			got := IsValidTransition(tc.from, tc.to)
			if got != tc.ok {
				t.Errorf("%s->%s: got %v, want %v", tc.from, tc.to, got, tc.ok)
			}
		})
	}
}

func TestIsTerminal(t *testing.T) {
	tests := []struct {
		state string
		want  bool
	}{
		{"idea", false},
		{"ready", false},
		{"in_progress", false},
		{"review", false},
		{"done", true},
		{"discarded", true},
		{"", false},
	}
	for _, tc := range tests {
		t.Run(tc.state, func(t *testing.T) {
			if got := IsTerminal(tc.state); got != tc.want {
				t.Errorf("IsTerminal(%q) = %v, want %v", tc.state, got, tc.want)
			}
		})
	}
}
