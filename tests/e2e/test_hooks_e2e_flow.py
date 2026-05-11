"""E2E: hook events drive session status (Notification → awaiting, Stop → idle).

Post-F5 (ADR-0017): start session through the task modal, not via a
worktree-direct button.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_hooks_e2e_status_changes_via_simulated_hook(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    expect(page).to_have_title("J-arvis")

    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator("text=demo").first).to_be_visible()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Hook flow")
    page.get_by_role("button", name="Criar").click()

    page.locator("text=Hook flow").first.click()
    page.get_by_role("button", name="Iniciar sessão").click()
    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Hook flow")
    page.get_by_label("close").click()

    sessions_resp = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions_resp[0]["id"]
    debug_resp = page.evaluate(
        f"async () => (await fetch('/api/_debug/token/{sid}')).json()"
    )
    token = debug_resp["token"]

    # Post-F4 the UI doesn't display session.status text directly (kanban
    # is task-centric; lib/format.ts orphan). We verify the hook plumbing
    # via the API: each hook POST must change session.status server-side.
    page.evaluate(
        "async (t) => fetch(`/api/hooks/Notification/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ message: 'need input' }) })",
        token,
    )
    all_sessions = page.evaluate(
        "async () => (await fetch('/api/sessions')).json()"
    )
    status = next(s for s in all_sessions if s["id"] == sid)
    assert status["status"] == "awaiting_response", status

    page.evaluate(
        "async (t) => fetch(`/api/hooks/Stop/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ reason: 'end' }) })",
        token,
    )
    all_sessions = page.evaluate(
        "async () => (await fetch('/api/sessions')).json()"
    )
    status = next(s for s in all_sessions if s["id"] == sid)
    assert status["status"] == "idle", status
