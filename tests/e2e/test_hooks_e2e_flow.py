import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_hooks_e2e_status_changes_via_simulated_hook(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    expect(page).to_have_title("J-arvis")

    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.get_by_role("heading", name="demo")).to_be_visible()

    page.get_by_label("start-main").click()
    expect(page.get_by_text("Em execução")).to_be_visible()

    sessions_resp = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions_resp[0]["id"]
    debug_resp = page.evaluate(
        f"async () => (await fetch('/api/_debug/token/{sid}')).json()"
    )
    token = debug_resp["token"]

    page.evaluate(
        "async (t) => fetch(`/api/hooks/Notification/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ message: 'need input' }) })",
        token,
    )
    expect(page.get_by_text("Aguardando resposta")).to_be_visible()

    page.evaluate(
        "async (t) => fetch(`/api/hooks/Stop/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ reason: 'end' }) })",
        token,
    )
    expect(page.get_by_text("Ocioso")).to_be_visible()
