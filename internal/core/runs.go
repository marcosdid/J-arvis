package core

import (
	"context"
	"errors"
	"fmt"
	"os/exec"
	"sort"

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
