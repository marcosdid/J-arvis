import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_full_flow_add_project_start_session_stop(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    expect(page).to_have_title("J-arvis")

    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()

    project_heading = page.get_by_role("heading", name="demo")
    expect(project_heading).to_be_visible()

    expect(page.get_by_label("start-main")).to_be_visible()
    expect(page.get_by_label("start-feature")).to_be_visible()

    page.get_by_label("start-main").click()
    expect(page.get_by_text("Em execução")).to_be_visible()

    stop_button = page.locator('button[aria-label^="stop-"]').first
    stop_button.click()
    expect(page.get_by_text("Concluído")).to_be_visible()
