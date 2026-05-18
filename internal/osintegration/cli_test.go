package osintegration

import (
	"reflect"
	"testing"
)

func TestParseFlags(t *testing.T) {
	cases := []struct {
		name string
		args []string
		want CLIFlags
	}{
		{"no args", []string{"jarvis"}, CLIFlags{}},
		{"--focus", []string{"jarvis", "--focus"}, CLIFlags{Focus: true}},
		{"unknown args ignored", []string{"jarvis", "--xxx", "yyy"}, CLIFlags{}},
		{"focus with extras", []string{"jarvis", "--focus", "--task=t1"}, CLIFlags{Focus: true}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := parseArgs(c.args)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("parseArgs(%v) = %+v, want %+v", c.args, got, c.want)
			}
		})
	}
}
