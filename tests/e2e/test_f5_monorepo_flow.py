"""F5 E2E: monorepo full lifecycle.

⚠️ Cannot run from inside ai-jail (gotcha #9). User runs manually from host:
    uv run pytest tests/e2e/test_f5_monorepo_flow.py -v

Flow:
1. Add monorepo project via drawer → header reports "monorepo".
2. Create task in NewTaskForm → appears in Backlog.
3. Open task modal → Iniciar sessão → task auto-moves to In Progress.
4. Reopen drawer → 1 task-group with 1 worktree row, branch matches slug.
5. Stop session via API (no UI for stop yet).
6. Move task → done via modal → drawer worktree disappears.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f5_monorepo_full_lifecycle(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)

    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator('[role="dialog"][aria-label="projects-drawer"]')).to_be_visible()
    page.get_by_label("project-name").fill("mono")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator(".project-node strong", has_text="mono")).to_be_visible()
    expect(page.locator(".project-node").filter(has_text="monorepo")).to_be_visible()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Add login")
    page.get_by_role("button", name="Criar").click()
    expect(page.locator('[data-testid="column-Backlog"]')).to_contain_text("Add login")

    page.locator("text=Add login").first.click()
    expect(page.locator('[role="dialog"]')).to_be_visible()
    page.get_by_role("button", name="Iniciar sessão").click()
    expect(
        page.locator('[data-testid="column-In Progress"]')
    ).to_contain_text("Add login")
    page.get_by_label("close").click()

    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator(".task-group").filter(has_text="Add login")).to_be_visible()
    wt_rows = page.locator(".task-group .wt-row")
    expect(wt_rows).to_have_count(1)
    expect(wt_rows.first.locator(".branch")).to_have_text("add-login")
    page.get_by_label("close-drawer").click()

    sessions = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions[0]["id"]
    page.evaluate(
        f"async () => fetch('/api/sessions/{sid}/stop', {{ method: 'POST' }})"
    )

    # in_progress → review → done (transitions.ts forbids in_progress→done directly)
    page.locator("text=Add login").first.click()
    page.select_option('[aria-label="move to"]', "review")
    expect(page.locator('[data-testid="column-Review"]')).to_contain_text("Add login")
    page.select_option('[aria-label="move to"]', "done")
    expect(page.locator('[data-testid="column-Done"]')).to_contain_text("Add login")
    page.get_by_label("close").click()

    # After cleanup, the task's worktree is gone (no .task-group).
    # Pre-existing worktrees (primary + `feature` from the fixture) remain
    # as orphans — list_project_worktrees doesn't filter the primary
    # checkout; that's a known F5 gap, not a regression.
    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator(".task-group")).to_have_count(0)
