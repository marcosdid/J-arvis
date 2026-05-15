package git

import (
	"context"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func initRepo(t *testing.T) string {
	t.Helper()
	d := t.TempDir()
	mustRun := func(args ...string) {
		out, err := exec.Command("git", append([]string{"-C", d}, args...)...).CombinedOutput()
		if err != nil {
			t.Fatalf("git %v: %v\nout: %s", args, err, string(out))
		}
	}
	mustRun("init", "-q")
	mustRun("-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "init")
	return d
}

func TestSubprocessOps_List_Empty(t *testing.T) {
	repo := initRepo(t)
	ops := NewSubprocessOps()
	infos, err := ops.List(context.Background(), repo)
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(infos) != 1 {
		t.Fatalf("expected 1 worktree (main), got %d: %+v", len(infos), infos)
	}
}

func TestSubprocessOps_AddListRemove_RoundTrip(t *testing.T) {
	repo := initRepo(t)
	wt := filepath.Join(t.TempDir(), "wt-feature")
	ops := NewSubprocessOps()

	if err := ops.Add(context.Background(), repo, wt, "feature/x"); err != nil {
		t.Fatalf("Add: %v", err)
	}

	infos, err := ops.List(context.Background(), repo)
	if err != nil {
		t.Fatalf("List after add: %v", err)
	}
	var found *WorktreeInfo
	for i := range infos {
		if infos[i].Path == wt {
			found = &infos[i]
		}
	}
	if found == nil {
		t.Fatalf("added worktree %s not in list: %+v", wt, infos)
	}
	if found.Branch == nil || *found.Branch != "feature/x" {
		t.Errorf("branch: got %v, want feature/x", found.Branch)
	}

	if err := ops.Remove(context.Background(), repo, wt, true); err != nil {
		t.Fatalf("Remove: %v", err)
	}

	infos, _ = ops.List(context.Background(), repo)
	for _, i := range infos {
		if i.Path == wt {
			t.Errorf("worktree %s still present after Remove: %+v", wt, i)
		}
	}
}

func TestSubprocessOps_Remove_AlreadyGone_IsAlreadyRemovedErr(t *testing.T) {
	repo := initRepo(t)
	ops := NewSubprocessOps()
	bogus := filepath.Join(t.TempDir(), "never-existed")
	err := ops.Remove(context.Background(), repo, bogus, false)
	if err == nil {
		t.Fatal("expected error removing non-existent worktree, got nil")
	}
	if !IsAlreadyRemovedErr(err) {
		t.Errorf("expected IsAlreadyRemovedErr=true, got false; err=%v", err)
	}
}

func TestParseWorktreeList_DetachedHEAD(t *testing.T) {
	out := "worktree /tmp/repo\nHEAD abc123\ndetached\n\n"
	infos := parseWorktreeList(out)
	if len(infos) != 1 {
		t.Fatalf("want 1, got %d", len(infos))
	}
	if infos[0].Branch != nil {
		t.Errorf("detached worktree should have Branch=nil, got %v", *infos[0].Branch)
	}
}

func TestParseWorktreeList_MultipleBlocks(t *testing.T) {
	out := strings.Join([]string{
		"worktree /tmp/main",
		"HEAD abc",
		"branch refs/heads/main",
		"",
		"worktree /tmp/feat",
		"HEAD def",
		"branch refs/heads/feature/x",
		"",
	}, "\n")
	infos := parseWorktreeList(out)
	if len(infos) != 2 {
		t.Fatalf("want 2, got %d: %+v", len(infos), infos)
	}
	if infos[0].Path != "/tmp/main" || *infos[1].Branch != "feature/x" {
		t.Errorf("parse mismatch: %+v", infos)
	}
}
