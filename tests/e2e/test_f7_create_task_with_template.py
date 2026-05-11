"""F7 E2E: criar task com template aplica prefix + grava profile + badges visíveis.

⚠️ Cannot run from inside ai-jail (gotcha #9). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f7_create_task_with_template.py -v
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f7_create_task_with_template_frontend(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    url, repo_path = orchestrator_with_repo
    page.goto(url)

    # Cria projeto via drawer
    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("p")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    # Preenche título + escolhe template frontend
    page.fill('[aria-label="título"]', "Add dark mode toggle")
    page.select_option('[aria-label="template"]', "frontend")

    # Hint mostra branch derivado do prefix
    expect(page.locator('[aria-label="template-hint"]')).to_contain_text(
        "feat-ui/add-dark-mode-toggle"
    )

    page.get_by_role("button", name="Criar").click()

    # Card aparece com badges
    card = page.locator(".task-card").filter(has_text="Add dark mode toggle").first
    expect(card.locator('[data-template-name="frontend"]')).to_be_visible()
    expect(card.locator('[data-permission-profile="yolo"]')).to_be_visible()
