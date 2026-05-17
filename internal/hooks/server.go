package hooks

import (
	"encoding/json"
	"net/http"
	"strings"
)

// SessionUpdater is the slice of store.SessionsRepo that the hook handler
// needs. Defined here (not in store) so hooks can be tested without a real DB.
type SessionUpdater interface {
	// UpdateStatus returns the previous status (or "" if the session has none)
	// and updates the row to next. Errors abort the request with 500.
	UpdateStatus(sessionID, next string) (previous string, err error)
	// BumpLastHookAt updates last_hook_at to NOW for sessionID.
	BumpLastHookAt(sessionID string) error
}

// EventBus is the slice of events.Emitter the handler uses.
type EventBus interface {
	Emit(name string, payload any)
}

// Handler implements http.Handler. The listener that hosts it lives in
// internal/localhttp; mount with `localSrv.Mount("/api/hooks/", handler)`.
type Handler struct {
	registry *TokenRegistry
	bus      EventBus
	updater  SessionUpdater
	mux      *http.ServeMux
}

func NewHandler(registry *TokenRegistry, bus EventBus, updater SessionUpdater) *Handler {
	h := &Handler{registry: registry, bus: bus, updater: updater, mux: http.NewServeMux()}
	h.mount(h.mux)
	return h
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h.mux.ServeHTTP(w, r)
}

func (h *Handler) mount(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/hooks/Notification/{token}", h.handleNotification)
	mux.HandleFunc("POST /api/hooks/PreToolUse/{token}", h.handlePreToolUse)
	mux.HandleFunc("POST /api/hooks/Stop/{token}", h.handleStop)
}

func (h *Handler) handleNotification(w http.ResponseWriter, r *http.Request) {
	sid, ok := h.resolveToken(r)
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
	prev, err := h.updater.UpdateStatus(sid, next)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if prev != next {
		h.bus.Emit("session.status_changed", map[string]any{
			"id": sid, "previous": prev, "current": next,
		})
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) handlePreToolUse(w http.ResponseWriter, r *http.Request) {
	sid, ok := h.resolveToken(r)
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
	if err := h.updater.BumpLastHookAt(sid); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.bus.Emit("session.tool_use", map[string]any{"id": sid, "tool": tool})
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]bool{"continue": true})
}

func (h *Handler) handleStop(w http.ResponseWriter, r *http.Request) {
	sid, ok := h.resolveToken(r)
	if !ok {
		http.NotFound(w, r)
		return
	}
	payload, _ := decodePayload(r)
	next, _ := ParseStop(payload)
	prev, err := h.updater.UpdateStatus(sid, next)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if prev != next {
		h.bus.Emit("session.status_changed", map[string]any{
			"id": sid, "previous": prev, "current": next,
		})
	}
	// NOTE: deliberate deviation from Python: do NOT emit session.stopped here.
	// That event is reserved for the manual SessionsService.Stop path. Hook-driven
	// Stop means "claude finished its turn" — subprocess is still alive awaiting
	// next user input.
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) resolveToken(r *http.Request) (string, bool) {
	tok := r.PathValue("token")
	if tok == "" {
		return "", false
	}
	return h.registry.Resolve(tok)
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
