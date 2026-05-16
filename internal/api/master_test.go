package api

import (
	"context"
	"os"
	"testing"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

func TestMasterAPI_Smoke_StartStop(t *testing.T) {
	// MasterAPI is a thin delegator; behavioural coverage lives in internal/core/master_test.go
	// (which already has 9 tests including round-trip integration).
	//
	// To write a smoke test here, we'd need to wire an in-memory SQLite DB,
	// a fake masterSession, and bypass sandboxCheck. Since sandboxCheck is
	// unexported, we can't inject it from the api package.
	//
	// Simplest path: rely on core/master_test.go for behavioural coverage.
	t.Skip("MasterAPI is a thin delegator; behavioural coverage lives in internal/core/master_test.go")
	_ = os.Getpid
	_ = context.Background
	_ = store.NewMasterSessionRepo
	_ = core.NewMasterService
	_ = events.FakeEmitter{}
}
