"""E2E: Kanban happy path + edge cases.

⚠️ Cannot run from inside ai-jail (gotcha #9). User runs manually from host:
    uv run pytest tests/e2e/test_kanban_e2e_flow.py -v

Pre-requisitos:
- Docker daemon up
- testcontainers + Playwright drivers installed (`playwright install chromium`)
- ui/dist built (`pnpm --dir ui run build`)
"""
import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_kanban_happy_path(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Criar task → mover pra Ready via modal → Iniciar sessão (NullSessionRuntime)
    → auto In Progress → drag pra Review → Done."""
    url, repo_path = orchestrator_with_repo

    # Seed project + worktree via UI so kanban has a worktree to pick
    page.goto(url)
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.get_by_role("heading", name="demo")).to_be_visible()

    # Kanban board renders
    expect(page.locator('[data-testid="column-Backlog"]')).to_be_visible()

    # Criar task via NewTaskForm
    page.fill('[aria-label="título"]', "Adicionar dark mode")
    page.click('button:has-text("Criar")')

    # Aparece em Backlog
    backlog = page.locator('[data-testid="column-Backlog"]')
    expect(backlog).to_contain_text("Adicionar dark mode")

    # Click → modal abre → Move to "ready" via dropdown
    page.click('text=Adicionar dark mode')
    expect(page.locator('[role="dialog"]')).to_be_visible()
    page.select_option('[aria-label="move to"]', "ready")
    page.click('[aria-label="close"]')

    # Reopen + Iniciar sessão
    page.click('text=Adicionar dark mode')
    page.select_option('[aria-label="worktree"]', index=1)
    page.click('button:has-text("Iniciar sessão")')

    # Card auto-moveu pra In Progress
    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Adicionar dark mode")

    # Drag In Progress → Review
    src = inprog.locator('[data-task-id]').first
    review = page.locator('[data-testid="column-Review"]')
    src.drag_to(review)
    expect(review).to_contain_text("Adicionar dark mode")

    # Drag Review → Done
    src = review.locator('[data-task-id]').first
    done = page.locator('[data-testid="column-Done"]')
    src.drag_to(done)
    expect(done).to_contain_text("Adicionar dark mode")


@pytest.mark.e2e
def test_quick_session_creates_task(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Click Quick session no drawer → task implícita aparece em In Progress."""
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    page.get_by_label("project-name").fill("demo-qs")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.get_by_role("heading", name="demo-qs")).to_be_visible()

    page.click('button:has-text("Projetos ▾")')
    expect(page.locator('[role="dialog"][aria-label="projects-drawer"]')).to_be_visible()
    page.locator('button:has-text("▶ Quick session")').first.click()

    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Quick session")


@pytest.mark.e2e
def test_invalid_drag_snaps_back(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Drag de Done → Backlog snap-back + toast 'Transição não permitida'."""
    # Skeleton — full impl requires setup helper that seeds a task already in Done
    pytest.skip("Skeleton — needs setup helper to seed a task in Done state")


@pytest.mark.e2e
def test_filter_persists_across_reload(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Filtra por projeto → reload → filtro permanece (localStorage)."""
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    page.get_by_label("project-name").fill("projA")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.get_by_role("heading", name="projA")).to_be_visible()

    # Click projA chip in filters
    page.click('button.chip:has-text("projA")')
    page.reload()

    # projA chip should still be active — chip has class "chip active", so match substring
    chip = page.locator('button.chip:has-text("projA")')
    expect(chip).to_have_class(re.compile(r"active"))


@pytest.mark.e2e
def test_double_iniciar_returns_409_toast(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Iniciar sessão + tentar iniciar segunda → toast 'já tem sessão ativa'."""
    pytest.skip("Skeleton — needs setup helper to seed an active session on a task")


@pytest.mark.e2e
def test_project_delete_blocked_with_tasks(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Tentar deletar project com tasks → toast 'Descarte as tasks…'."""
    pytest.skip("Skeleton — needs setup helper to seed tasks on a project")
