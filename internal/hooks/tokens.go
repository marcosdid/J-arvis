package hooks

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
)

// TokenRegistry maps opaque tokens to session IDs. In-memory only; restart
// loses all tokens (subprocesses also die on restart, so no recovery is
// meaningful). Safe for concurrent access via RWMutex.
type TokenRegistry struct {
	mu sync.RWMutex
	m  map[string]string
}

func NewTokenRegistry() *TokenRegistry {
	return &TokenRegistry{m: map[string]string{}}
}

// Generate returns a fresh 64-hex-char (256-bit) token and registers it
// against sessionID. Deliberate upgrade from Python uuid4().hex (128 bits).
func (r *TokenRegistry) Generate(sessionID string) string {
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		// crypto/rand failure on Linux means the OS is in a degenerate state;
		// panic is appropriate (no meaningful recovery).
		panic("crypto/rand.Read: " + err.Error())
	}
	tok := hex.EncodeToString(b[:])
	r.mu.Lock()
	r.m[tok] = sessionID
	r.mu.Unlock()
	return tok
}

func (r *TokenRegistry) Resolve(token string) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	sid, ok := r.m[token]
	return sid, ok
}

func (r *TokenRegistry) Revoke(token string) {
	r.mu.Lock()
	delete(r.m, token)
	r.mu.Unlock()
}

// FindBySessionID is a reverse-lookup helper used by tests and the e2e_http
// __token debug route. Returns "" if not found. Linear scan; the registry is
// small enough that no extra indexing is justified.
func (r *TokenRegistry) FindBySessionID(sessionID string) string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for tok, sid := range r.m {
		if sid == sessionID {
			return tok
		}
	}
	return ""
}
