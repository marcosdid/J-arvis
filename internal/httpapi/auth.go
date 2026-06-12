// Package httpapi serves the app APIs over loopback HTTP. F11.1: promoted
// from the e2e_http template so production, dev and Playwright share one
// transport (spec: 2026-06-12-f11-electron-http-first-design.md).
package httpapi

import (
	"crypto/subtle"
	"net/http"
)

// RequireToken guards routes with the boot-generated app token. Accepts
// `Authorization: Bearer <t>` or `?token=<t>` — EventSource cannot set
// headers, so SSE authenticates via query param. An empty configured
// token rejects everything (fail-closed if boot wiring breaks).
func RequireToken(token string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodOptions { // CORS preflight carries no auth
			next.ServeHTTP(w, r)
			return
		}
		authOK := subtle.ConstantTimeCompare([]byte(r.Header.Get("Authorization")), []byte("Bearer "+token)) == 1
		queryOK := subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("token")), []byte(token)) == 1
		if token != "" && (authOK || queryOK) {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"unauthorized"}`))
	})
}
