package core

import (
	"errors"
	"net"
	"strconv"
	"sync"
)

const (
	MinPort = 31000
	MaxPort = 31999
)

var ErrNoFreePort = errors.New("runs: no free port in 31000-31999")

type PortAllocator struct {
	mu       sync.Mutex
	reserved map[int]bool
}

func NewPortAllocator() *PortAllocator {
	return &PortAllocator{reserved: map[int]bool{}}
}

// Allocate finds the next free port in [MinPort, MaxPort] not already reserved
// AND not bound by any other process (probed via net.Listen).
func (p *PortAllocator) Allocate() (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for port := MinPort; port <= MaxPort; port++ {
		if p.reserved[port] {
			continue
		}
		ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(port))
		if err != nil {
			continue // bound by another process
		}
		_ = ln.Close()
		p.reserved[port] = true
		return port, nil
	}
	return 0, ErrNoFreePort
}

func (p *PortAllocator) Release(port int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.reserved, port)
}

// Reserve marks a port as in-use without probing. Used on boot to load ports
// from active DB rows so they aren't re-handed-out.
func (p *PortAllocator) Reserve(port int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.reserved[port] = true
}
