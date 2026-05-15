package hooks

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"time"
)

// SessionUpdater is the slice of store.SessionsRepo that the hook server needs.
// Defined here (not in store) so hooks can be tested without a real DB.
type SessionUpdater interface {
	// UpdateStatus returns the previous status (or "" if the session has none)
	// and updates the row to next. Errors abort the request with 500.
	UpdateStatus(sessionID, next string) (previous string, err error)
	// BumpLastHookAt updates last_hook_at to NOW for sessionID.
	BumpLastHookAt(sessionID string) error
}

// EventBus is the slice of events.Emitter the server uses.
type EventBus interface {
	Emit(name string, payload any)
}

type Server struct {
	registry *TokenRegistry
	bus      EventBus
	updater  SessionUpdater
	srv      *http.Server
	listener net.Listener
	baseURL  string
}

func NewServer(registry *TokenRegistry, bus EventBus, updater SessionUpdater) *Server {
	return &Server{registry: registry, bus: bus, updater: updater}
}

// Start binds 127.0.0.1:0 and serves until Stop. Returns the bound port.
func (s *Server) Start() (int, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, fmt.Errorf("hooks bind: %w", err)
	}
	s.listener = ln
	port := ln.Addr().(*net.TCPAddr).Port
	s.baseURL = fmt.Sprintf("http://127.0.0.1:%d", port)

	mux := http.NewServeMux()
	s.mount(mux)
	s.srv = &http.Server{
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}

	go func() {
		if err := s.srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("hooks server: %v", err)
		}
	}()
	return port, nil
}

func (s *Server) BaseURL() string { return s.baseURL }

func (s *Server) Stop() error {
	if s.srv == nil {
		return nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return s.srv.Shutdown(ctx)
}

// Started reports whether Start succeeded (used by main.go for sandbox_available).
func (s *Server) Started() bool { return s.listener != nil }

func (s *Server) mount(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/hooks/Notification/{token}", s.handleNotification)
	mux.HandleFunc("POST /api/hooks/PreToolUse/{token}", s.handlePreToolUse)
	mux.HandleFunc("POST /api/hooks/Stop/{token}", s.handleStop)
}

func (s *Server) handleNotification(w http.ResponseWriter, r *http.Request) {
	sid, ok := s.resolveToken(r)
	if !ok {
		http.NotFound(w, r)
		return
	}
	payload, err := decodePayload(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	next, err := ParseNotification(payload)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnprocessableEntity)
		return
	}
	prev, err := s.updater.UpdateStatus(sid, next)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if prev != next {
		s.bus.Emit("session.status_changed", map[string]any{
			"id": sid, "previous": prev, "current": next,
		})
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) handlePreToolUse(w http.ResponseWriter, r *http.Request) {
	sid, ok := s.resolveToken(r)
	if !ok {
		http.NotFound(w, r)
		return
	}
	payload, err := decodePayload(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	tool, err := ParsePreToolUse(payload)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnprocessableEntity)
		return
	}
	if err := s.updater.BumpLastHookAt(sid); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	s.bus.Emit("session.tool_use", map[string]any{"id": sid, "tool": tool})
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]bool{"continue": true})
}

func (s *Server) handleStop(w http.ResponseWriter, r *http.Request) {
	sid, ok := s.resolveToken(r)
	if !ok {
		http.NotFound(w, r)
		return
	}
	payload, _ := decodePayload(r)
	next, _ := ParseStop(payload)
	prev, err := s.updater.UpdateStatus(sid, next)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if prev != next {
		s.bus.Emit("session.status_changed", map[string]any{
			"id": sid, "previous": prev, "current": next,
		})
	}
	// NOTE: deliberate deviation from Python: do NOT emit session.stopped here.
	// That event is reserved for the manual SessionsService.Stop path. Hook-driven
	// Stop means "claude finished its turn" — subprocess is still alive awaiting
	// next user input.
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) resolveToken(r *http.Request) (string, bool) {
	tok := r.PathValue("token")
	if tok == "" {
		return "", false
	}
	return s.registry.Resolve(tok)
}

func decodePayload(r *http.Request) (map[string]any, error) {
	if r.Body == nil {
		return map[string]any{}, nil
	}
	var p map[string]any
	// Do NOT call dec.DisallowUnknownFields() — claude payloads carry extra
	// fields like `cwd`, `session_id`, `transcript_path` that we ignore.
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&p); err != nil {
		if strings.Contains(err.Error(), "EOF") {
			return map[string]any{}, nil
		}
		return nil, err
	}
	return p, nil
}
