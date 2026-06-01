package main

import "net/http"

// noCacheMiddleware injects `Cache-Control: no-store` on every response so the
// WebKitGTK runtime that Wails uses on Linux never persists embedded assets
// between launches. Without this, the WebKit disk cache at
// ~/.cache/<app>/WebKitCache serves stale bundles after each rebuild, even
// though `go:embed` already pinned fresh bytes into the binary.
func noCacheMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}
