package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// noCacheMiddleware should set Cache-Control: no-store on every response so
// WebKitGTK never serves a stale embedded asset across rebuilds.
func TestNoCacheMiddleware_SetsNoStoreOnEveryResponse(t *testing.T) {
	called := false
	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("hello"))
	})

	handler := noCacheMiddleware(next)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/index.html", nil)
	handler.ServeHTTP(rec, req)

	if !called {
		t.Fatal("middleware did not call next handler")
	}
	got := rec.Header().Get("Cache-Control")
	if got != "no-store" {
		t.Errorf("Cache-Control=%q, want %q", got, "no-store")
	}
}

func TestNoCacheMiddleware_PreservesBodyAndStatus(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusTeapot)
		_, _ = w.Write([]byte("brewing"))
	})

	handler := noCacheMiddleware(next)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTeapot {
		t.Errorf("status=%d, want 418", rec.Code)
	}
	if rec.Body.String() != "brewing" {
		t.Errorf("body=%q, want %q", rec.Body.String(), "brewing")
	}
}
