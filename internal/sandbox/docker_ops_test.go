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

// argvCapture replaces the exec seam so tests can assert the exact argv.
type argvCapture struct {
	calls [][]string
}

func (a *argvCapture) cmd(_ context.Context, name string, args ...string) (string, error) {
	a.calls = append(a.calls, append([]string{name}, args...))
	return "fake-stdout", nil
}

func equalSlices(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestSubprocessDockerOps_Build_ArgvShape(t *testing.T) {
	cap := &argvCapture{}
	s := &SubprocessDockerOps{commandFn: cap.cmd}
	if err := s.Build(context.Background(), "/tmp/proj", "myimg:dev"); err != nil {
		t.Fatalf("Build: %v", err)
	}
	if len(cap.calls) != 1 {
		t.Fatalf("calls=%d, want 1", len(cap.calls))
	}
	want := []string{"docker", "build", "-t", "myimg:dev", "/tmp/proj"}
	if !equalSlices(cap.calls[0], want) {
		t.Errorf("argv=%v, want %v", cap.calls[0], want)
	}
}

func TestSubprocessDockerOps_NetworkCreate_ArgvShape(t *testing.T) {
	cap := &argvCapture{}
	s := &SubprocessDockerOps{commandFn: cap.cmd}
	_ = s.NetworkCreate(context.Background(), "jarvis-run-abc12345")
	want := []string{"docker", "network", "create", "--driver", "bridge", "jarvis-run-abc12345"}
	if !equalSlices(cap.calls[0], want) {
		t.Errorf("argv=%v, want %v", cap.calls[0], want)
	}
}

func TestSubprocessDockerOps_NetworkRm_ArgvShape(t *testing.T) {
	cap := &argvCapture{}
	s := &SubprocessDockerOps{commandFn: cap.cmd}
	_ = s.NetworkRm(context.Background(), "jarvis-run-abc12345")
	want := []string{"docker", "network", "rm", "jarvis-run-abc12345"}
	if !equalSlices(cap.calls[0], want) {
		t.Errorf("argv=%v, want %v", cap.calls[0], want)
	}
}

func TestSubprocessDockerOps_Stop_ArgvShape(t *testing.T) {
	cap := &argvCapture{}
	s := &SubprocessDockerOps{commandFn: cap.cmd}
	_ = s.Stop(context.Background(), "cid-1")
	want := []string{"docker", "stop", "--time", "10", "cid-1"}
	if !equalSlices(cap.calls[0], want) {
		t.Errorf("argv=%v, want %v", cap.calls[0], want)
	}
}

func TestSubprocessDockerOps_Rm_ArgvShape(t *testing.T) {
	cap := &argvCapture{}
	s := &SubprocessDockerOps{commandFn: cap.cmd}
	_ = s.Rm(context.Background(), "cid-1")
	want := []string{"docker", "rm", "-f", "cid-1"}
	if !equalSlices(cap.calls[0], want) {
		t.Errorf("argv=%v, want %v", cap.calls[0], want)
	}
}
