package core

import (
	"errors"
	"net"
	"strconv"
	"testing"
)

func TestPortAllocator_Allocate_InRange(t *testing.T) {
	pa := NewPortAllocator()
	p, err := pa.Allocate()
	if err != nil {
		t.Fatalf("Allocate: %v", err)
	}
	if p < MinPort || p > MaxPort {
		t.Errorf("port=%d out of range [%d, %d]", p, MinPort, MaxPort)
	}
}

func TestPortAllocator_Release_FreesPort(t *testing.T) {
	pa := NewPortAllocator()
	p, _ := pa.Allocate()
	pa.Release(p)
	// After release, the same port should be allocatable again. Reserve every
	// other port first to force the allocator to revisit p.
	for i := MinPort; i <= MaxPort; i++ {
		if i != p {
			pa.Reserve(i)
		}
	}
	p2, err := pa.Allocate()
	if err != nil {
		t.Fatalf("Allocate after Release: %v", err)
	}
	if p2 != p {
		t.Errorf("got port %d, expected %d (only free slot)", p2, p)
	}
}

func TestPortAllocator_Reserve_BlocksAllocation(t *testing.T) {
	pa := NewPortAllocator()
	pa.Reserve(MinPort)
	p, _ := pa.Allocate()
	if p == MinPort {
		t.Errorf("Allocate handed out reserved port %d", p)
	}
}

func TestPortAllocator_Exhaustion_ReturnsErrNoFreePort(t *testing.T) {
	pa := NewPortAllocator()
	for i := MinPort; i <= MaxPort; i++ {
		pa.Reserve(i)
	}
	_, err := pa.Allocate()
	if !errors.Is(err, ErrNoFreePort) {
		t.Errorf("err=%v, want ErrNoFreePort", err)
	}
}

func TestPortAllocator_SocketProbe_SkipsExternallyHeldPort(t *testing.T) {
	pa := NewPortAllocator()
	// Hold MinPort externally (simulates another process)
	ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(MinPort))
	if err != nil {
		t.Skipf("could not bind %d for test: %v", MinPort, err)
	}
	defer ln.Close()

	p, err := pa.Allocate()
	if err != nil {
		t.Fatalf("Allocate: %v", err)
	}
	if p == MinPort {
		t.Errorf("Allocate returned externally-held port %d", p)
	}
}
