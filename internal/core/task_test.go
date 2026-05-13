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
