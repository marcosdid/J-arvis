"""F6 E2E: BootstrapModal dispara quando manifesto ausente.

⚠️ Cannot run from inside ai-jail (gotcha #9). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f6_bootstrap_missing_manifest.py -v

Flow:
1. Project sem `.orchestrator/run.yml`.
2. Click ▶ Run → POST /api/tasks/{id}/runs retorna 422 manifest_missing
   com `bootstrap_url`.
3. UI abre BootstrapModal.
4. Click "Iniciar bootstrap" → POST /api/tasks/{id}/bootstrap-manifest
   → 202. Backend spawna sessão Claude (FakeSessionRuntime apenas registra).
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f6_bootstrap_modal_opens_on_missing_manifest(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)

    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("no-manifest")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Demo bootstrap")
    page.get_by_role("button", name="Criar").click()

    page.locator("text=Demo bootstrap").first.click()
    page.select_option('[aria-label="move to"]', "ready")
    page.get_by_role("button", name="Iniciar sessão").click()
    page.get_by_label("close").click()

    # Click ▶ Run — backend retorna 422 manifest_missing → modal abre
    page.locator('button[aria-label^="run-start-"]').first.click()

    expect(
        page.locator('[role="dialog"][aria-label="bootstrap-manifest-modal"]'),
    ).to_be_visible(timeout=10_000)

    expect(page.locator('text=/Manifesto faltando/i')).to_be_visible()
    expect(
        page.get_by_role("button", name="Iniciar bootstrap"),
    ).to_be_visible()
