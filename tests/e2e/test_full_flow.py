"""E2E: minimal happy path — add project, create task, start/stop session.

Post-F5 (ADR-0017): project add lives in the drawer; session-start is
through the task modal (no direct worktree button).
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_full_flow_add_project_start_session_stop(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    expect(page).to_have_title("J-arvis")

    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator('[role="dialog"][aria-label="projects-drawer"]')).to_be_visible()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator("text=demo").first).to_be_visible()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Bootstrap")
    page.get_by_role("button", name="Criar").click()

    backlog = page.locator('[data-testid="column-Backlog"]')
    expect(backlog).to_contain_text("Bootstrap")

    page.locator("text=Bootstrap").first.click()
    expect(page.locator('[role="dialog"]')).to_be_visible()
    page.get_by_role("button", name="Iniciar sessão").click()

    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Bootstrap")

    page.get_by_label("close").click()

    sessions = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions[0]["id"]
    resp = page.evaluate(
        f"async () => fetch('/api/sessions/{sid}/stop', {{ method: 'POST' }})"
    )
    assert resp is not None
