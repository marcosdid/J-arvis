package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func okHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
}

func TestRequireToken(t *testing.T) {
	h := RequireToken("s3cret", okHandler())

	cases := []struct {
		name   string
		header string
		query  string
		want   int
	}{
		{"no token", "", "", http.StatusUnauthorized},
		{"wrong header", "Bearer nope", "", http.StatusUnauthorized},
		{"valid header", "Bearer s3cret", "", http.StatusOK},
		{"valid query (SSE)", "", "?token=s3cret", http.StatusOK},
		{"wrong query", "", "?token=nope", http.StatusUnauthorized},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("POST", "/api/x"+tc.query, nil)
			if tc.header != "" {
				req.Header.Set("Authorization", tc.header)
			}
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, req)
			if rec.Code != tc.want {
				t.Fatalf("got %d want %d", rec.Code, tc.want)
			}
			if tc.want == http.StatusUnauthorized && rec.Header().Get("Content-Type") != "application/json" {
				t.Fatalf("401 Content-Type: got %q want application/json", rec.Header().Get("Content-Type"))
			}
		})
	}
}

func TestRequireTokenEmptyTokenRejectsAll(t *testing.T) {
	h := RequireToken("", okHandler())
	req := httptest.NewRequest("POST", "/api/x?token=", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("empty token must reject: got %d", rec.Code)
	}
}

func TestRequireTokenAllowsCORSPreflight(t *testing.T) {
	h := RequireToken("s3cret", okHandler())
	req := httptest.NewRequest(http.MethodOptions, "/api/x", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("OPTIONS preflight must pass: got %d", rec.Code)
	}
}
