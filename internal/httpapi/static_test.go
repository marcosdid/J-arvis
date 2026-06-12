package httpapi

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
)

func TestSPAHandler(t *testing.T) {
	dist := fstest.MapFS{
		"index.html":    {Data: []byte("<html>jarvis</html>")},
		"assets/app.js": {Data: []byte("console.log(1)")},
	}
	ts := httptest.NewServer(SPAHandler(dist))
	defer ts.Close()

	get := func(p string) (int, string) {
		res, err := http.Get(ts.URL + p)
		if err != nil {
			t.Fatal(err)
		}
		defer res.Body.Close()
		b, _ := io.ReadAll(res.Body)
		return res.StatusCode, string(b)
	}

	if code, body := get("/"); code != 200 || !strings.Contains(body, "jarvis") {
		t.Fatalf("root: %d %q", code, body)
	}
	if code, _ := get("/assets/app.js"); code != 200 {
		t.Fatalf("asset: %d", code)
	}
	// SPA fallback: unknown client-side route serves index.html
	if code, body := get("/tasks/abc"); code != 200 || !strings.Contains(body, "jarvis") {
		t.Fatalf("fallback: %d %q", code, body)
	}
}

func TestSPAHandlerDirectoryDoesNotList(t *testing.T) {
	// assets/ has no index.html: http.FileServerFS would autoindex it and
	// leak every build filename. A directory path must fall back to the SPA
	// index, never produce a listing.
	dist := fstest.MapFS{
		"index.html":    {Data: []byte("<html>jarvis</html>")},
		"assets/app.js": {Data: []byte("console.log(1)")},
	}
	ts := httptest.NewServer(SPAHandler(dist))
	defer ts.Close()

	res, err := http.Get(ts.URL + "/assets")
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()
	b, _ := io.ReadAll(res.Body)
	body := string(b)

	if res.StatusCode != 200 {
		t.Fatalf("dir: %d", res.StatusCode)
	}
	if !strings.Contains(body, "jarvis") {
		t.Fatalf("dir should serve index.html, got %q", body)
	}
	if strings.Contains(body, "app.js") {
		t.Fatalf("dir leaked a file listing: %q", body)
	}
}
