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
