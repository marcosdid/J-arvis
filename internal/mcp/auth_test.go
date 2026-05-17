package mcp

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestNewBearerTokenIsBase64UrlAndAtLeast32Bytes(t *testing.T) {
	tok := NewBearerToken()
	v := tok.Value()
	if len(v) < 40 { // 32 random bytes → ~43 chars in base64url unpadded
		t.Errorf("token len=%d, want >= 40", len(v))
	}
	if strings.ContainsAny(v, "+/=") {
		t.Errorf("token %q must be base64url (no +, /, =)", v)
	}
}

func TestValidateAcceptsExactValue(t *testing.T) {
	tok := NewBearerToken()
	if !tok.Validate(tok.Value()) {
		t.Error("Validate(own value) = false")
	}
}

func TestValidateRejectsOthers(t *testing.T) {
	tok := NewBearerToken()
	if tok.Validate("") {
		t.Error("Validate(\"\") = true")
	}
	if tok.Validate("not-the-token") {
		t.Error("Validate(garbage) = true")
	}
}

func TestTwoTokensDiffer(t *testing.T) {
	a := NewBearerToken()
	b := NewBearerToken()
	if a.Value() == b.Value() {
		t.Error("two NewBearerToken() returned identical values")
	}
}

func TestAuthMiddleware401WhenHeaderMissing(t *testing.T) {
	tok := NewBearerToken()
	inner := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(200)
	})
	mw := authMiddleware(tok, inner)
	rec := httptest.NewRecorder()
	mw.ServeHTTP(rec, httptest.NewRequest("POST", "/api/mcp", strings.NewReader("{}")))
	if rec.Code != 401 {
		t.Errorf("code=%d, want 401", rec.Code)
	}
	body, _ := io.ReadAll(rec.Body)
	if !strings.Contains(string(body), "missing bearer token") {
		t.Errorf("body=%q, want 'missing bearer token'", body)
	}
}

func TestAuthMiddleware401WhenTokenWrong(t *testing.T) {
	tok := NewBearerToken()
	inner := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(200) })
	mw := authMiddleware(tok, inner)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/mcp", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer garbage")
	mw.ServeHTTP(rec, req)
	if rec.Code != 401 {
		t.Errorf("code=%d, want 401", rec.Code)
	}
}

func TestAuthMiddlewareDelegatesWhenTokenCorrect(t *testing.T) {
	tok := NewBearerToken()
	called := false
	inner := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		called = true
		w.WriteHeader(200)
	})
	mw := authMiddleware(tok, inner)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/mcp", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer "+tok.Value())
	mw.ServeHTTP(rec, req)
	if !called {
		t.Error("inner handler not called")
	}
	if rec.Code != 200 {
		t.Errorf("code=%d, want 200", rec.Code)
	}
}
