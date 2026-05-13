package core

import (
	"context"
	"database/sql"
	"errors"
	"testing"

	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

func setupSyncFixture(t *testing.T) (
	*sql.DB, string, []store.Repository, *fakeGit, *events.FakeEmitter, *WorktreesService,
) {
	t.Helper()
	db := newTestStoreDB(t)
	projectsRepo := store.NewProjectsRepo(db)
	reposRepo := store.NewRepositoriesRepo(db)
	p, _ := projectsRepo.Create(context.Background(), store.CreateProjectInput{
		Name: "proj", Path: "/tmp/proj",
	})
	created, _ := reposRepo.CreateBulk(context.Background(), p.ID, []store.RepoSpecInput{
		{Name: "proj", SubPath: "."},
	})
	fake := newFakeGit()
	bus := &events.FakeEmitter{}
	svc := NewWorktreesService(
		store.NewWorktreesRepo(db), reposRepo, projectsRepo, fake, bus,
	)
	return db, p.ID, created, fake, bus, svc
}

func TestSyncProjectWorktrees_DiscoversOrphan(t *testing.T) {
	_, projectID, _, fake, bus, svc := setupSyncFixture(t)
	branch := "main"
	fake.ListResults["/tmp/proj"] = []jgit.WorktreeInfo{
		{Path: "/tmp/proj", Branch: &branch},
		{Path: "/tmp/proj-feat", Branch: ptrTo("feature/x")},
	}
	wts, err := svc.SyncProjectWorktrees(context.Background(), projectID)
	if err != nil {
		t.Fatalf("Sync: %v", err)
	}
	if len(wts) != 2 {
		t.Errorf("want 2 worktrees, got %d", len(wts))
	}
	created := 0
	for _, c := range bus.Calls {
		if c.Name == "worktree.created" {
			created++
		}
	}
	if created != 2 {
		t.Errorf("expected 2 worktree.created emits, got %d (calls: %+v)", created, bus.Calls)
	}
}

func TestSyncProjectWorktrees_UpdatesBranchOnExisting(t *testing.T) {
	db, projectID, repos, fake, _, svc := setupSyncFixture(t)
	old := "old"
	_, _ = store.NewWorktreesRepo(db).Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/proj-x", Branch: &old,
	})
	fake.ListResults["/tmp/proj"] = []jgit.WorktreeInfo{
		{Path: "/tmp/proj-x", Branch: ptrTo("new-branch")},
	}
	got, err := svc.SyncProjectWorktrees(context.Background(), projectID)
	if err != nil {
		t.Fatalf("Sync: %v", err)
	}
	if len(got) != 1 || got[0].Branch == nil || *got[0].Branch != "new-branch" {
		t.Errorf("branch not updated: %+v", got)
	}
}

func TestSyncProjectWorktrees_ProjectNotFound(t *testing.T) {
	_, _, _, _, _, svc := setupSyncFixture(t)
	_, err := svc.SyncProjectWorktrees(context.Background(), "bogus-project-id")
	if !errors.Is(err, store.ErrProjectNotFound) {
		t.Errorf("want ErrProjectNotFound, got %v", err)
	}
}

func TestCleanupForTask_HappyPath(t *testing.T) {
	db, projectID, repos, fake, bus, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "t",
	})
	wtRepo := store.NewWorktreesRepo(db)
	_, _ = wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-a", TaskID: &tk.ID,
	})
	bus.Calls = nil
	if err := svc.CleanupForTask(context.Background(), tk.ID); err != nil {
		t.Fatalf("CleanupForTask: %v", err)
	}
	rmCalls := 0
	for _, c := range fake.Calls {
		if c.Op == "remove" {
			rmCalls++
		}
	}
	if rmCalls != 1 {
		t.Errorf("expected 1 remove call, got %d (%s)", rmCalls, fakeCalls(fake.Calls))
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "worktree.removed" {
		t.Errorf("expected worktree.removed emit, got %+v", bus.Calls)
	}
	got, _ := wtRepo.ListByTask(context.Background(), tk.ID)
	if len(got) != 0 {
		t.Errorf("expected 0 worktrees for task, got %+v", got)
	}
}

func TestCleanupForTask_GitFailure_OrphansRow_AndEmitsOrphaned(t *testing.T) {
	db, projectID, repos, fake, bus, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "t",
	})
	wtRepo := store.NewWorktreesRepo(db)
	id, _ := wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-fail", TaskID: &tk.ID,
	})
	fake.RemoveErrors["/tmp/wt-fail"] = genericRemoveErr()
	bus.Calls = nil

	if err := svc.CleanupForTask(context.Background(), tk.ID); err != nil {
		t.Fatalf("CleanupForTask should not propagate err; got %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "worktree.orphaned" {
		t.Errorf("expected worktree.orphaned emit, got %+v", bus.Calls)
	}
	w, _ := wtRepo.GetByID(context.Background(), id)
	if w.TaskID != nil {
		t.Errorf("row not orphaned: task_id=%v", *w.TaskID)
	}
}

func TestCleanupForTask_AlreadyRemoved_IsIdempotentSuccess(t *testing.T) {
	db, projectID, repos, fake, bus, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "t",
	})
	wtRepo := store.NewWorktreesRepo(db)
	_, _ = wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-ghost", TaskID: &tk.ID,
	})
	fake.RemoveErrors["/tmp/wt-ghost"] = alreadyRemovedErr()
	bus.Calls = nil

	if err := svc.CleanupForTask(context.Background(), tk.ID); err != nil {
		t.Fatalf("CleanupForTask: %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "worktree.removed" {
		t.Errorf("expected worktree.removed (idempotent), got %+v", bus.Calls)
	}
	got, _ := wtRepo.ListByTask(context.Background(), tk.ID)
	if len(got) != 0 {
		t.Errorf("row should be deleted, got %+v", got)
	}
}

func TestDeleteOrphan_RejectsOwnedWorktree(t *testing.T) {
	db, projectID, repos, _, _, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "t",
	})
	wtRepo := store.NewWorktreesRepo(db)
	id, _ := wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-owned", TaskID: &tk.ID,
	})
	err := svc.DeleteOrphan(context.Background(), id)
	if !errors.Is(err, WorktreeNotOrphanError) {
		t.Errorf("want WorktreeNotOrphanError, got %v", err)
	}
}

func TestDeleteOrphan_HappyPath(t *testing.T) {
	db, _, repos, _, bus, svc := setupSyncFixture(t)
	wtRepo := store.NewWorktreesRepo(db)
	id, _ := wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-orphan",
	})
	bus.Calls = nil
	if err := svc.DeleteOrphan(context.Background(), id); err != nil {
		t.Fatalf("DeleteOrphan: %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "worktree.removed" {
		t.Errorf("expected worktree.removed, got %+v", bus.Calls)
	}
}

func TestDeleteOrphan_GitErrorPropagates(t *testing.T) {
	db, _, repos, fake, _, svc := setupSyncFixture(t)
	wtRepo := store.NewWorktreesRepo(db)
	id, _ := wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-fail",
	})
	fake.RemoveErrors["/tmp/wt-fail"] = genericRemoveErr()
	err := svc.DeleteOrphan(context.Background(), id)
	if err == nil {
		t.Fatal("expected propagated git error")
	}
}

func TestDeleteOrphan_AlreadyGone_IsIdempotent(t *testing.T) {
	db, _, repos, fake, bus, svc := setupSyncFixture(t)
	wtRepo := store.NewWorktreesRepo(db)
	id, _ := wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-ghost",
	})
	fake.RemoveErrors["/tmp/wt-ghost"] = alreadyRemovedErr()
	bus.Calls = nil
	if err := svc.DeleteOrphan(context.Background(), id); err != nil {
		t.Fatalf("DeleteOrphan: %v", err)
	}
	if _, err := wtRepo.GetByID(context.Background(), id); !errors.Is(err, store.ErrWorktreeNotFound) {
		t.Errorf("row not deleted")
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "worktree.removed" {
		t.Errorf("expected worktree.removed, got %+v", bus.Calls)
	}
}

func ptrTo[T any](v T) *T { return &v }

func TestCreateForTask_Monorepo(t *testing.T) {
	db, projectID, repos, fake, _, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, err := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "implement-X",
	})
	if err != nil {
		t.Fatalf("seed task: %v", err)
	}

	wts, err := svc.CreateForTask(context.Background(), tk.ID, "feat/x")
	if err != nil {
		t.Fatalf("CreateForTask: %v", err)
	}
	if len(wts) != 1 {
		t.Fatalf("want 1 worktree (monorepo), got %d", len(wts))
	}
	if wts[0].RepositoryID != repos[0].ID {
		t.Errorf("repo: got %s, want %s", wts[0].RepositoryID, repos[0].ID)
	}

	addCount := 0
	for _, c := range fake.Calls {
		if c.Op == "add" {
			addCount++
		}
	}
	if addCount != 1 {
		t.Errorf("want 1 git-add call, got %d", addCount)
	}
}

func TestCreateForTask_RejectsIfTaskHasWorktrees(t *testing.T) {
	db, projectID, repos, _, _, svc := setupSyncFixture(t)
	tasksRepo := store.NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: projectID, Title: "x",
	})
	wtRepo := store.NewWorktreesRepo(db)
	tid := tk.ID
	_, _ = wtRepo.Upsert(context.Background(), store.WorktreeUpsert{
		RepositoryID: repos[0].ID, Path: "/tmp/wt-x", TaskID: &tid,
	})
	_, err := svc.CreateForTask(context.Background(), tk.ID, "feat/x")
	if !errors.Is(err, ErrTaskAlreadyHasWorktrees) {
		t.Errorf("want ErrTaskAlreadyHasWorktrees, got %v", err)
	}
}

func TestBranchSlug(t *testing.T) {
	tests := []struct {
		in, want string
	}{
		{"feat/new-thing", "feat-new-thing"},
		{"main", "main"},
		{"x y z", "x-y-z"},
		{"feat/foo/bar", "feat-foo-bar"},
	}
	for _, tc := range tests {
		if got := branchSlug(tc.in); got != tc.want {
			t.Errorf("branchSlug(%q): got %q, want %q", tc.in, got, tc.want)
		}
	}
}
