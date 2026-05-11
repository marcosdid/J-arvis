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

    page.goto(url)

    # Seed project via drawer (post-F5: project add lives in drawer)
    page.click('button:has-text("Projetos ▾")')
    expect(page.locator('[role="dialog"][aria-label="projects-drawer"]')).to_be_visible()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator("text=demo").first).to_be_visible()
    page.get_by_label("close-drawer").click()

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

    # Reopen + Iniciar sessão (post-F5: no worktree picker)
    page.click('text=Adicionar dark mode')
    page.click('button:has-text("Iniciar sessão")')

    # Card auto-moveu pra In Progress
    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Adicionar dark mode")

    # Drag In Progress → Review. dnd-kit now uses activationConstraint
    # distance=8 (preserves card-click semantics); Playwright's single-step
    # drag_to() jumps too fast for dnd-kit's pointermove to register, so
    # we drive the mouse manually with steps to simulate real movement.
    def manual_drag(src_locator, target_locator) -> None:
        src_box = src_locator.bounding_box()
        tgt_box = target_locator.bounding_box()
        assert src_box and tgt_box
        page.mouse.move(
            src_box["x"] + src_box["width"] / 2,
            src_box["y"] + src_box["height"] / 2,
        )
        page.mouse.down()
        page.mouse.move(
            tgt_box["x"] + tgt_box["width"] / 2,
            tgt_box["y"] + tgt_box["height"] / 2,
            steps=20,
        )
        page.mouse.up()

    src = inprog.locator('[data-task-id]').first
    review = page.locator('[data-testid="column-Review"]')
    manual_drag(src, review)
    expect(review).to_contain_text("Adicionar dark mode")

    # F5 guard: stop session before moving to terminal state (done/discarded)
    sessions = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions[0]["id"]
    page.evaluate(
        f"async () => fetch('/api/sessions/{sid}/stop', {{ method: 'POST' }})"
    )

    # Drag Review → Done
    src = review.locator('[data-task-id]').first
    done = page.locator('[data-testid="column-Done"]')
    manual_drag(src, done)
    expect(done).to_contain_text("Adicionar dark mode")


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
    page.click('button:has-text("Projetos ▾")')
    page.get_by_label("project-name").fill("projA")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator("text=projA").first).to_be_visible()
    page.get_by_label("close-drawer").click()

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
