package core

var validTransitions = map[string]map[string]bool{
	"idea":        {"ready": true, "discarded": true, "idea": true},
	"ready":       {"in_progress": true, "idea": true, "discarded": true, "ready": true},
	"in_progress": {"review": true, "ready": true, "discarded": true, "in_progress": true},
	"review":      {"done": true, "in_progress": true, "discarded": true, "review": true},
	"done":        {"discarded": true, "done": true},
	"discarded":   {"discarded": true},
}

func IsValidTransition(from, to string) bool {
	return validTransitions[from][to]
}
