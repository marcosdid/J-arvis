package core

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

var (
	ErrTaskHasActiveRun  = errors.New("runs: task already has an active run")
	ErrTaskNotEligible   = errors.New("runs: task state does not allow runs (must be in_progress or review)")
	ErrDockerUnavailable = errors.New("runs: docker CLI not available")
	ErrRunNotFound       = store.ErrRunNotFound
	ErrCircularDeps      = errors.New("runs: manifest has circular depends_on")
)

type runsTasksRepo interface {
	Get(ctx context.Context, id string) (*store.Task, error)
}

type runsWorktreesRepo interface {
	ListByTask(ctx context.Context, taskID string) ([]store.Worktree, error)
}

type runsProjectsRepo interface {
	GetByID(ctx context.Context, id string) (*store.Project, error)
}

type RunsService struct {
	repo        *store.RunsRepo
	docker      sandbox.DockerOps
	allocator   *PortAllocator
	tasks       runsTasksRepo
	worktrees   runsWorktreesRepo
	projects    runsProjectsRepo
	bus         events.Emitter
	dockerCheck func() error // injectable for tests
}

func NewRunsService(
	repo *store.RunsRepo, docker sandbox.DockerOps, allocator *PortAllocator,
	tasks runsTasksRepo, worktrees runsWorktreesRepo, projects runsProjectsRepo,
	bus events.Emitter,
) *RunsService {
	return &RunsService{
		repo:        repo,
		docker:      docker,
		allocator:   allocator,
		tasks:       tasks,
		worktrees:   worktrees,
		projects:    projects,
		bus:         bus,
		dockerCheck: defaultDockerCheck,
	}
}

func defaultDockerCheck() error {
	if _, err := exec.LookPath("docker"); err != nil {
		return fmt.Errorf("%w: %v", ErrDockerUnavailable, err)
	}
	return nil
}

// topoSort returns service names ordered so deps come before dependents.
// Kahn's algorithm with sorted insertion for determinism.
func topoSort(services map[string]ServiceSpec) ([]string, error) {
	// in-degree[name] = number of services that `name` depends on (incoming edges).
	indeg := map[string]int{}
	for name, spec := range services {
		indeg[name] = len(spec.DependsOn)
	}

	// Queue of services with in-degree 0.
	var queue []string
	for name, deg := range indeg {
		if deg == 0 {
			queue = append(queue, name)
		}
	}
	sort.Strings(queue)

	var order []string
	for len(queue) > 0 {
		curr := queue[0]
		queue = queue[1:]
		order = append(order, curr)
		var newlyReady []string
		for name, spec := range services {
			for _, dep := range spec.DependsOn {
				if dep == curr {
					indeg[name]--
					if indeg[name] == 0 {
						newlyReady = append(newlyReady, name)
					}
				}
			}
		}
		sort.Strings(newlyReady)
		queue = append(queue, newlyReady...)
		sort.Strings(queue)
	}

	if len(order) != len(services) {
		return nil, fmt.Errorf("%w: stuck after %d/%d", ErrCircularDeps, len(order), len(services))
	}
	return order, nil
}

// DeriveRunCWD returns the working directory for a Run.
//
// Order:
//  1. If the task has any active worktree, use its path.
//     Multi-worktree: use the parent dir (shared parent by F10.3).
//  2. Otherwise, derive from project.path + branch slug.
//     e.g. /projects/myapp + "feat/x" → /projects/myapp-feat-x
func (s *RunsService) DeriveRunCWD(ctx context.Context, taskID string) (string, error) {
	task, err := s.tasks.Get(ctx, taskID)
	if err != nil {
		return "", err
	}
	wts, err := s.worktrees.ListByTask(ctx, taskID)
	if err != nil {
		return "", err
	}
	if len(wts) > 0 {
		if len(wts) > 1 {
			return filepath.Dir(wts[0].Path), nil
		}
		return wts[0].Path, nil
	}
	proj, err := s.projects.GetByID(ctx, task.ProjectID)
	if err != nil {
		return "", err
	}
	branch := ""
	if task.Branch != nil {
		branch = *task.Branch
	}
	slug := strings.ReplaceAll(branch, "/", "-")
	return proj.Path + "-" + slug, nil
}

func (s *RunsService) StartRun(ctx context.Context, taskID string) (*store.Run, error) {
	// 1. Preflight: docker.
	if err := s.dockerCheck(); err != nil {
		return nil, err
	}

	// 2. Task guards.
	task, err := s.tasks.Get(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if IsTerminal(task.State) {
		return nil, ErrTaskNotEligible
	}

	// 3. Run guard (1 active per task).
	if existing, err := s.repo.GetActiveByTask(ctx, taskID); err == nil && existing != nil {
		return nil, ErrTaskHasActiveRun
	}

	// 4. Derive CWD.
	cwd, err := s.DeriveRunCWD(ctx, taskID)
	if err != nil {
		return nil, err
	}

	// 5. Load + validate manifest.
	manifest, err := LoadManifest(cwd)
	if err != nil {
		return nil, err
	}
	if err := manifest.Validate(); err != nil {
		return nil, err
	}

	// 6. Topo sort.
	order, err := topoSort(manifest.Services)
	if err != nil {
		return nil, err
	}

	// 7. Allocate ports.
	ports := map[string]int{}
	var allocated []int
	for _, svc := range order {
		spec := manifest.Services[svc]
		if spec.Port == 0 {
			continue
		}
		p, err := s.allocator.Allocate()
		if err != nil {
			for _, alloc := range allocated {
				s.allocator.Release(alloc)
			}
			return nil, err
		}
		ports[svc] = p
		allocated = append(allocated, p)
	}

	// 8. Substitutions per service.
	runID := uuid.NewString()
	resolved := make(map[string]ServiceSpec, len(manifest.Services))
	for svc, spec := range manifest.Services {
		if spec.Env != nil {
			spec.Env = ResolveSubstitutions(spec.Env, ports, runID, cwd)
		}
		resolved[svc] = spec
	}

	// 9. Insert run row.
	portsJSON, _ := json.Marshal(ports)
	run := store.Run{
		ID:           runID,
		TaskID:       taskID,
		Status:       "pending",
		Cwd:          cwd,
		ManifestPath: filepath.Join(cwd, ".orchestrator/run.yml"),
		PortsJSON:    string(portsJSON),
		NetworkName:  "jarvis-run-" + runID[:8],
		StartedAt:    time.Now().UTC(),
	}
	if err := s.repo.Insert(ctx, run); err != nil {
		for _, alloc := range allocated {
			s.allocator.Release(alloc)
		}
		return nil, err
	}
	s.emitStatus(&run, "", "pending")

	// 10. Build.
	s.transition(&run, "building")
	for _, svc := range order {
		spec := resolved[svc]
		if spec.Build == "" {
			continue
		}
		tag := "jarvis-run-" + runID[:8] + "-" + svc
		if err := s.docker.Build(ctx, filepath.Join(cwd, spec.Build), tag); err != nil {
			s.rollback(ctx, &run, nil, "", allocated, err.Error())
			return nil, err
		}
	}

	// 11. Network create.
	if err := s.docker.NetworkCreate(ctx, run.NetworkName); err != nil {
		s.rollback(ctx, &run, nil, "", allocated, err.Error())
		return nil, err
	}

	// 12. Container starts.
	containerIDs := map[string]string{}
	for _, svc := range order {
		spec := resolved[svc]
		cs := buildContainerSpec(svc, spec, run, ports[svc])
		cid, err := s.docker.ContainerStart(ctx, cs)
		if err != nil {
			s.rollback(ctx, &run, containerIDs, run.NetworkName, allocated, err.Error())
			return nil, err
		}
		containerIDs[svc] = cid
		if spec.Healthcheck != nil {
			if err := s.waitHealthy(ctx, cid, spec.Healthcheck); err != nil {
				s.rollback(ctx, &run, containerIDs, run.NetworkName, allocated, "healthcheck timeout: "+svc)
				return nil, err
			}
		}
	}

	// 13. Seeds.
	s.transition(&run, "seeding")
	for _, svc := range order {
		spec := resolved[svc]
		if spec.Seed == nil {
			continue
		}
		timeout := spec.Seed.Timeout
		if timeout == 0 {
			timeout = 60 * time.Second
		}
		if err := s.docker.RunInContainer(ctx, containerIDs[svc], spec.Seed.Command, timeout); err != nil {
			s.rollback(ctx, &run, containerIDs, run.NetworkName, allocated, "seed failed: "+svc+": "+err.Error())
			return nil, err
		}
	}

	// 14. Persist final state.
	cidsJSON, _ := json.Marshal(containerIDs)
	run.ContainersJSON = string(cidsJSON)
	_ = s.repo.UpdateContainerIDs(ctx, run.ID, run.ContainersJSON)
	s.transition(&run, "ready")
	return &run, nil
}

func buildContainerSpec(svc string, spec ServiceSpec, run store.Run, hostPort int) sandbox.ContainerSpec {
	cs := sandbox.ContainerSpec{
		Image:        spec.Image,
		Name:         run.NetworkName + "-" + svc,
		Network:      run.NetworkName,
		NetworkAlias: svc,
		Env:          spec.Env,
	}
	if spec.Build != "" {
		cs.Image = "jarvis-run-" + run.ID[:8] + "-" + svc
	}
	if hostPort > 0 && spec.Port > 0 {
		cs.PortMap = map[int]int{hostPort: spec.Port}
	}
	mount := false
	if spec.MountSource != nil {
		mount = *spec.MountSource
	} else {
		mount = spec.Build != ""
	}
	if mount {
		cs.Volumes = map[string]string{filepath.Join(run.Cwd, spec.Build): "/workspace"}
	}
	return cs
}

func (s *RunsService) waitHealthy(ctx context.Context, cid string, hc *HealthcheckSpec) error {
	interval := hc.Interval
	if interval == 0 {
		interval = 5 * time.Second
	}
	retries := hc.Retries
	if retries == 0 {
		retries = 10
	}
	for i := 0; i < retries; i++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		status, _ := s.docker.ContainerHealthStatus(ctx, cid)
		if status == "healthy" {
			return nil
		}
		time.Sleep(interval)
	}
	return fmt.Errorf("healthcheck timeout (interval=%v retries=%d)", interval, retries)
}

func (s *RunsService) transition(run *store.Run, status string) {
	old := run.Status
	run.Status = status
	_ = s.repo.UpdateStatus(context.Background(), run.ID, status)
	s.emitStatus(run, old, status)
}

func (s *RunsService) emitStatus(run *store.Run, old, current string) {
	s.bus.Emit("run.status_changed", map[string]any{
		"run_id":   run.ID,
		"task_id":  run.TaskID,
		"previous": old,
		"current":  current,
	})
}

// rollback (3-layer best-effort). Real impl will be expanded in Stage 6.
func (s *RunsService) rollback(ctx context.Context, run *store.Run, containerIDs map[string]string, networkName string, ports []int, errMsg string) {
	for _, cid := range containerIDs {
		_ = s.docker.Stop(ctx, cid)
		_ = s.docker.Rm(ctx, cid)
	}
	if networkName != "" {
		_ = s.docker.NetworkRm(ctx, networkName)
	}
	for _, p := range ports {
		s.allocator.Release(p)
	}
	_ = s.repo.MarkFailed(ctx, run.ID, errMsg)
	s.emitStatus(run, run.Status, "failed")
}
