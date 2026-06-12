package httpapi

import (
	"io/fs"
	"net/http"
	"path"
	"strings"
)

// SPAHandler serves the embedded ui/dist with index.html fallback so
// client-side routes deep-link correctly. F11.1: mounted but the Wails
// asset server still owns the production window; F11.2 makes this the
// only UI origin.
func SPAHandler(dist fs.FS) http.Handler {
	fileServer := http.FileServerFS(dist)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := strings.TrimPrefix(path.Clean(r.URL.Path), "/")
		if p != "" {
			if _, err := fs.Stat(dist, p); err != nil {
				r.URL.Path = "/" // SPA fallback
			}
		}
		fileServer.ServeHTTP(w, r)
	})
}
