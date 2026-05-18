package osintegration

import "os"

// CLIFlags carries parsed command-line flags for the jarvis binary.
// Manual parsing (not flag.Parse) keeps it trivial to mock and avoids
// conflict with Wails CLI runner. Unknown args are ignored silently
// (forward compat for future flags).
type CLIFlags struct {
	// Focus is set when --focus is passed. Today the OnSecondInstanceLaunch
	// handler always focuses regardless of flag — Focus is documented intent
	// for the future when args could navigate to a specific task.
	Focus bool
}

// ParseFlags reads os.Args directly. Use parseArgs for tests.
func ParseFlags() CLIFlags { return parseArgs(os.Args) }

func parseArgs(args []string) CLIFlags {
	var f CLIFlags
	for _, arg := range args[1:] {
		switch arg {
		case "--focus":
			f.Focus = true
		}
	}
	return f
}
