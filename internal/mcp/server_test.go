package mcp

import (
	"net/http/httptest"
	"strings"
	"testing"
)

// TestHandlerRejects401WithoutAuth checks the auth middleware sits in front
// of the SDK handler. With no Authorization header, we must never reach the
// SDK. Services can be nil for this test — no tool dispatch happens.
func TestHandlerRejects401WithoutAuth(t *testing.T) {
	srv := NewServer(nil, nil, nil, NewBearerToken())
	rec := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rec, httptest.NewRequest("POST", "/api/mcp", strings.NewReader("{}")))
	if rec.Code != 401 {
		t.Errorf("code=%d, want 401", rec.Code)
	}
}

// TestNewServerExposesToken sanity-checks that Token() returns the same
// bearer that was injected, so main.go can pass it to spec-#2 wiring.
func TestNewServerExposesToken(t *testing.T) {
	tok := NewBearerToken()
	srv := NewServer(nil, nil, nil, tok)
	if srv.Token() != tok {
		t.Error("Token() did not return the injected BearerToken pointer")
	}
}
