package sandbox

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os/exec"
	"strings"
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

// cmdRunner is the seam for test injection. Production uses dockerCmdExec.
type cmdRunner func(ctx context.Context, name string, args ...string) (string, error)

// SubprocessDockerOps shells out via os/exec. Methods implemented in Tasks 3.2 and 3.3.
type SubprocessDockerOps struct {
	commandFn cmdRunner
}

func NewSubprocessDockerOps() *SubprocessDockerOps {
	return &SubprocessDockerOps{commandFn: dockerCmdExec}
}

func dockerCmdExec(ctx context.Context, name string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return stdout.String(), fmt.Errorf("docker %s: %w (stderr: %s)", strings.Join(args, " "), err, stderr.String())
	}
	return strings.TrimSpace(stdout.String()), nil
}

func (s *SubprocessDockerOps) Build(ctx context.Context, buildPath, imageTag string) error {
	_, err := s.commandFn(ctx, "docker", "build", "-t", imageTag, buildPath)
	return err
}

func (s *SubprocessDockerOps) NetworkCreate(ctx context.Context, name string) error {
	_, err := s.commandFn(ctx, "docker", "network", "create", "--driver", "bridge", name)
	return err
}

func (s *SubprocessDockerOps) NetworkRm(ctx context.Context, name string) error {
	_, err := s.commandFn(ctx, "docker", "network", "rm", name)
	return err
}

func (s *SubprocessDockerOps) Stop(ctx context.Context, containerID string) error {
	_, err := s.commandFn(ctx, "docker", "stop", "--time", "10", containerID)
	return err
}

func (s *SubprocessDockerOps) Rm(ctx context.Context, containerID string) error {
	_, err := s.commandFn(ctx, "docker", "rm", "-f", containerID)
	return err
}

// Keep the remaining 4 stubs (ContainerStart, RunInContainer, StreamLogs,
// ContainerHealthStatus) from Task 3.1 — Task 3.3 implements them.
func (s *SubprocessDockerOps) ContainerStart(context.Context, ContainerSpec) (string, error) { return "", nil }
func (s *SubprocessDockerOps) RunInContainer(context.Context, string, []string, time.Duration) error { return nil }
func (s *SubprocessDockerOps) StreamLogs(context.Context, string, io.Writer) error          { return nil }
func (s *SubprocessDockerOps) ContainerHealthStatus(context.Context, string) (string, error) { return "", nil }
