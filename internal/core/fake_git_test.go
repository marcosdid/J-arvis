package core

import (
	"context"
	"fmt"
	"sync"

	jgit "github.com/marcosdid/jarvis/internal/git"
)

type fakeGit struct {
	mu           sync.Mutex
	ListResults  map[string][]jgit.WorktreeInfo
	RemoveErrors map[string]error
	AddErrors    map[string]error
	Calls        []fakeCall
}

type fakeCall struct {
	Op     string
	Repo   string
	Target string
	Branch string
	Force  bool
}

func newFakeGit() *fakeGit {
	return &fakeGit{
		ListResults:  map[string][]jgit.WorktreeInfo{},
		RemoveErrors: map[string]error{},
		AddErrors:    map[string]error{},
	}
}

func (f *fakeGit) List(_ context.Context, repo string) ([]jgit.WorktreeInfo, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.Calls = append(f.Calls, fakeCall{Op: "list", Repo: repo})
	return f.ListResults[repo], nil
}

func (f *fakeGit) Add(_ context.Context, repo, target, branch string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.Calls = append(f.Calls, fakeCall{Op: "add", Repo: repo, Target: target, Branch: branch})
	if err, ok := f.AddErrors[target]; ok {
		return err
	}
	if err, ok := f.AddErrors["*"]; ok {
		return err
	}
	return nil
}

func (f *fakeGit) Remove(_ context.Context, repo, target string, force bool) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.Calls = append(f.Calls, fakeCall{Op: "remove", Repo: repo, Target: target, Force: force})
	if err, ok := f.RemoveErrors[target]; ok {
		return err
	}
	return nil
}

func alreadyRemovedErr() error {
	return &jgit.GitWorktreeError{
		Op: "remove", Repo: "/x", Stderr: "fatal: '/x' is not a working tree",
	}
}

func genericRemoveErr() error {
	return &jgit.GitWorktreeError{
		Op: "remove", Repo: "/x", Stderr: "fatal: permission denied",
	}
}

func fakeCalls(calls []fakeCall) string { return fmt.Sprintf("%+v", calls) }
