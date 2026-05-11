"""F6 E2E: simple Run flow with manifest pre-existing.

⚠️ Cannot run from inside ai-jail (gotcha #9). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f6_simple_run_flow.py -v

Flow:
1. Container started with project dir containing `.orchestrator/run.yml`.
2. Add project via drawer → create task → drag to ready → start session.
3. Click ▶ Run on TaskCard → wait for ready chip with URL.
4. Click ⏹ Stop → chip disappears, button voltta a ser ▶ Run.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f6_simple_run_lifecycle(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    """Task com manifesto preset (nginx single-service) → ▶ Run → ready
    → URL chip aparece → ⏹ Stop → estado idle."""
    url, repo_path = orchestrator_with_repo

    # Setup: escreve manifesto no repo do container via debug endpoint.
    # (O conftest fixture já preparou /tmp/repos/main com git init + commit;
    # aqui só assumimos que .orchestrator/run.yml será criado pelo bootstrap
    # OU pré-existe na fixture — caminho da fixture é monorepo simples, sem
    # manifest. Pra esse E2E vamos forçar via shell exec dentro do container.)
    # Nota: esta E2E presume que o conftest foi estendido pra criar
    # manifesto. Se não, marcará skip; user runs a partir do host com
    # estrutura pré-preparada.
    pytest.skip(
        "Requer fixture orchestrator_with_repo_and_manifest (estender F5 "
        "conftest pra escrever .orchestrator/run.yml com nginx). "
        "Implementar quando rodar do host pela 1ª vez.",
    )

    # Esqueleto do flow esperado:
    page.goto(url)
    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    page.fill('[aria-label="título"]', "Demo Run")
    page.get_by_role("button", name="Criar").click()

    page.locator("text=Demo Run").first.click()
    page.select_option('[aria-label="move to"]', "ready")
    page.get_by_role("button", name="Iniciar sessão").click()
    page.get_by_label("close").click()

    # ▶ Run no card
    run_btn = page.get_by_role("button", name=lambda n: "run-start" in (n or ""))
    run_btn.click()

    # Espera status ready (até 60s — build + healthcheck do nginx)
    expect(page.locator('.run-status[data-status="ready"]')).to_be_visible(timeout=60_000)
    # URL chip clicável visível
    expect(page.locator('a.run-url')).to_be_visible()

    # ⏹ Stop
    stop_btn = page.get_by_role("button", name=lambda n: "run-stop" in (n or ""))
    stop_btn.click()

    # Volta a botão ▶ Run
    expect(page.get_by_role("button", name=lambda n: "run-restart" in (n or ""))).to_be_visible(
        timeout=30_000,
    )
