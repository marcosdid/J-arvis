package sandbox

import (
	"context"
	"io"
	"testing"
	"time"
)

// Compile-time guard: SubprocessDockerOps must satisfy DockerOps.
var _ DockerOps = (*SubprocessDockerOps)(nil)

type fakeDocker struct {
	calls []string
}

func (f *fakeDocker) Build(_ context.Context, _, _ string) error { f.calls = append(f.calls, "Build"); return nil }
func (f *fakeDocker) NetworkCreate(_ context.Context, _ string) error { f.calls = append(f.calls, "NetworkCreate"); return nil }
func (f *fakeDocker) NetworkRm(_ context.Context, _ string) error     { f.calls = append(f.calls, "NetworkRm"); return nil }
func (f *fakeDocker) ContainerStart(_ context.Context, _ ContainerSpec) (string, error) { f.calls = append(f.calls, "ContainerStart"); return "fake-cid", nil }
func (f *fakeDocker) RunInContainer(_ context.Context, _ string, _ []string, _ time.Duration) error { f.calls = append(f.calls, "RunInContainer"); return nil }
func (f *fakeDocker) StreamLogs(_ context.Context, _ string, _ io.Writer) error { f.calls = append(f.calls, "StreamLogs"); return nil }
func (f *fakeDocker) Stop(_ context.Context, _ string) error                    { f.calls = append(f.calls, "Stop"); return nil }
func (f *fakeDocker) Rm(_ context.Context, _ string) error                      { f.calls = append(f.calls, "Rm"); return nil }
func (f *fakeDocker) ContainerHealthStatus(_ context.Context, _ string) (string, error) { f.calls = append(f.calls, "ContainerHealthStatus"); return "healthy", nil }

var _ DockerOps = (*fakeDocker)(nil)

func TestFakeDockerSatisfiesInterface(t *testing.T) {
	f := &fakeDocker{}
	_, _ = f.ContainerStart(context.Background(), ContainerSpec{})
	if len(f.calls) != 1 {
		t.Errorf("calls=%v", f.calls)
	}
}
