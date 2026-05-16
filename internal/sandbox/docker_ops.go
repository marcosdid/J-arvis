package sandbox

import (
	"context"
	"io"
	"time"
)

type DockerOps interface {
	Build(ctx context.Context, buildPath, imageTag string) error
	NetworkCreate(ctx context.Context, name string) error
	NetworkRm(ctx context.Context, name string) error
	ContainerStart(ctx context.Context, spec ContainerSpec) (string, error)
	RunInContainer(ctx context.Context, containerID string, command []string, timeout time.Duration) error
	StreamLogs(ctx context.Context, containerID string, dst io.Writer) error
	Stop(ctx context.Context, containerID string) error
	Rm(ctx context.Context, containerID string) error
	ContainerHealthStatus(ctx context.Context, containerID string) (string, error)
}

type ContainerSpec struct {
	Image        string
	Name         string
	Network      string
	NetworkAlias string
	PortMap      map[int]int
	Env          map[string]string
	Volumes      map[string]string
}

// SubprocessDockerOps shells out via os/exec. Methods implemented in Tasks 3.2 and 3.3.
type SubprocessDockerOps struct{}

func NewSubprocessDockerOps() *SubprocessDockerOps { return &SubprocessDockerOps{} }

// Stub methods — real impls in Tasks 3.2 and 3.3.
func (s *SubprocessDockerOps) Build(context.Context, string, string) error                  { return nil }
func (s *SubprocessDockerOps) NetworkCreate(context.Context, string) error                  { return nil }
func (s *SubprocessDockerOps) NetworkRm(context.Context, string) error                      { return nil }
func (s *SubprocessDockerOps) ContainerStart(context.Context, ContainerSpec) (string, error) { return "", nil }
func (s *SubprocessDockerOps) RunInContainer(context.Context, string, []string, time.Duration) error { return nil }
func (s *SubprocessDockerOps) StreamLogs(context.Context, string, io.Writer) error          { return nil }
func (s *SubprocessDockerOps) Stop(context.Context, string) error                           { return nil }
func (s *SubprocessDockerOps) Rm(context.Context, string) error                             { return nil }
func (s *SubprocessDockerOps) ContainerHealthStatus(context.Context, string) (string, error) { return "", nil }
