"""F5 E2E: multi-repo — 1 task spawns N worktrees, 1 session sees them.

⚠️ Cannot run from inside ai-jail (gotcha #9). User runs manually from host:
    uv run pytest tests/e2e/test_f5_multi_repo_flow.py -v

Flow:
1. Add multi-repo project (backend/ + frontend/, each with .git).
2. Project header reports "2 sub-repos".
3. Create task — leave default branch (auto-slug from title).
4. Iniciar sessão → daemon creates 2 worktrees (1 per sub-repo).
5. Drawer: 1 task-group with 2 wt rows, each `<repo>/<branch>`.
6. Stop session via API; move to done; drawer empty.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f5_multi_repo_one_session_two_worktrees(
    page: Page, orchestrator_with_multi_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_multi_repo

    page.goto(url)

    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("multi")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator(".project-node strong", has_text="multi")).to_be_visible()
    expect(
        page.locator(".project-node").filter(has_text="2 sub-repos")
    ).to_be_visible()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Add oauth")
    page.get_by_role("button", name="Criar").click()
    expect(page.locator('[data-testid="column-Backlog"]')).to_contain_text("Add oauth")

    page.locator("text=Add oauth").first.click()
    page.get_by_role("button", name="Iniciar sessão").click()
    expect(
        page.locator('[data-testid="column-In Progress"]')
    ).to_contain_text("Add oauth")
    page.get_by_label("close").click()

    page.get_by_role("button", name="Projetos ▾").click()
    task_group = page.locator(".task-group").filter(has_text="Add oauth")
    expect(task_group).to_be_visible()
    wt_rows = task_group.locator(".wt-row")
    expect(wt_rows).to_have_count(2)
    repo_names = wt_rows.locator(".repo-name")
    expect(repo_names).to_have_count(2)
    expect(repo_names.nth(0)).to_have_text("backend")
    expect(repo_names.nth(1)).to_have_text("frontend")
    expect(wt_rows.nth(0).locator(".branch")).to_have_text("add-oauth")
    expect(wt_rows.nth(1).locator(".branch")).to_have_text("add-oauth")
    page.get_by_label("close-drawer").click()

    sessions = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions[0]["id"]
    page.evaluate(
        f"async () => fetch('/api/sessions/{sid}/stop', {{ method: 'POST' }})"
    )

    # in_progress → review → done (transitions.ts forbids in_progress→done directly)
    page.locator("text=Add oauth").first.click()
    page.select_option('[aria-label="move to"]', "review")
    expect(page.locator('[data-testid="column-Review"]')).to_contain_text("Add oauth")
    page.select_option('[aria-label="move to"]', "done")
    expect(page.locator('[data-testid="column-Done"]')).to_contain_text("Add oauth")
    page.get_by_label("close").click()

    # After cleanup the task-group is gone. Sub-repo primary worktrees remain
    # as orphans (same F5 gap as monorepo flow — see test_f5_monorepo_flow).
    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator(".task-group")).to_have_count(0)
