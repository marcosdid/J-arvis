package mcp

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"log"
	"net/http"
	"strings"
)

// BearerToken is the single boot-generated secret that the MCP HTTP routes
// require on every request via "Authorization: Bearer <value>". It lives in
// memory only; restarting the daemon mints a fresh token. Spec #2 (master
// session upgrade) consumes Value() and writes it into the master session's
// .claude/settings.json so master-claude can call our tools.
type BearerToken struct{ value string }

// NewBearerToken mints a fresh 256-bit token encoded as URL-safe base64
// (unpadded). If crypto/rand fails — extraordinarily rare — the token
// stays empty and Validate always rejects, which is the right failure
// mode (the daemon won't accept any client until restarted).
func NewBearerToken() *BearerToken {
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		return &BearerToken{}
	}
	return &BearerToken{value: base64.RawURLEncoding.EncodeToString(b[:])}
}

// Value returns the token string for consumers writing it into settings.json
// or similar. Never log this anywhere user-visible.
func (t *BearerToken) Value() string { return t.value }

// Validate returns true iff s matches the token. Comparison is constant-time
// to avoid the classic timing side-channel.
func (t *BearerToken) Validate(s string) bool {
	if t.value == "" {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(t.value), []byte(s)) == 1
}

// authMiddleware wraps an http.Handler with bearer-token enforcement. Missing
// or wrong tokens get 401. Wrong tokens also log a warn line — useful when
// a fresh settings.json was written but the daemon was restarted (token
// mismatch).
func authMiddleware(tok *BearerToken, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hdr := r.Header.Get("Authorization")
		if !strings.HasPrefix(hdr, "Bearer ") {
			http.Error(w, `{"error":"missing bearer token"}`, http.StatusUnauthorized)
			return
		}
		if !tok.Validate(strings.TrimPrefix(hdr, "Bearer ")) {
			log.Printf("mcp: invalid bearer token from %s", r.RemoteAddr)
			http.Error(w, `{"error":"invalid bearer token"}`, http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r)
	})
}
