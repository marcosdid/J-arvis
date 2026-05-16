package sandbox

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os/exec"
	"sort"
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

func (s *SubprocessDockerOps) ContainerStart(ctx context.Context, spec ContainerSpec) (string, error) {
	args := []string{"run", "-d", "--name", spec.Name}
	if spec.Network != "" {
		args = append(args, "--network", spec.Network)
	}
	if spec.NetworkAlias != "" {
		args = append(args, "--network-alias", spec.NetworkAlias)
	}
	// Deterministic argv ordering across map iterations
	hostPorts := make([]int, 0, len(spec.PortMap))
	for hp := range spec.PortMap {
		hostPorts = append(hostPorts, hp)
	}
	sort.Ints(hostPorts)
	for _, hp := range hostPorts {
		args = append(args, "-p", fmt.Sprintf("%d:%d", hp, spec.PortMap[hp]))
	}
	envKeys := make([]string, 0, len(spec.Env))
	for k := range spec.Env {
		envKeys = append(envKeys, k)
	}
	sort.Strings(envKeys)
	for _, k := range envKeys {
		args = append(args, "-e", k+"="+spec.Env[k])
	}
	volKeys := make([]string, 0, len(spec.Volumes))
	for k := range spec.Volumes {
		volKeys = append(volKeys, k)
	}
	sort.Strings(volKeys)
	for _, k := range volKeys {
		args = append(args, "-v", k+":"+spec.Volumes[k])
	}
	args = append(args, spec.Image)
	return s.commandFn(ctx, "docker", args...)
}

func (s *SubprocessDockerOps) RunInContainer(ctx context.Context, containerID string, command []string, timeout time.Duration) error {
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	args := append([]string{"exec", containerID}, command...)
	_, err := s.commandFn(cctx, "docker", args...)
	return err
}

func (s *SubprocessDockerOps) ContainerHealthStatus(ctx context.Context, containerID string) (string, error) {
	return s.commandFn(ctx, "docker", "inspect", "--format", "{{.State.Health.Status}}", containerID)
}

// StreamLogs runs `docker logs -f` and pipes stdout to dst. Cancels via ctx.
// Doesn't go through commandFn because it uses pipe streaming (not buffered output).
// Integration test coverage in Stage 11.
func (s *SubprocessDockerOps) StreamLogs(ctx context.Context, containerID string, dst io.Writer) error {
	cmd := exec.CommandContext(ctx, "docker", "logs", "-f", containerID)
	cmd.Stdout = dst
	cmd.Stderr = dst
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start docker logs: %w", err)
	}
	return cmd.Wait()
}
