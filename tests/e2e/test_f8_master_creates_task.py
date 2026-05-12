"""F8 E2E: master cria task via chat no sidebar.

⚠️ Cannot run from inside ai-jail (gotcha #9). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f8_master_creates_task.py -v

Flow:
1. Abrir UI; MasterSidebar conecta WebSocket
2. Aguardar prompt do Claude master aparecer no xterm
3. Digitar "Crie task 'Demo F8' no projeto X com template frontend" via xterm
4. Aguardar Claude responder + executar create_task MCP tool
5. Verificar task apareceu no Kanban
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f8_master_creates_task_via_chat(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)

    # Sidebar aparece
    expect(page.locator('[aria-label="master-session"]')).to_be_visible()
    expect(page.get_by_text("Claude master")).to_be_visible()

    # Cria projeto via drawer
    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    # Espera o terminal renderizar prompt do Claude (até 30s)
    page.wait_for_function(
        """() => {
            const term = window.__masterTerm;
            if (!term) return false;
            const buffer = term.buffer.active;
            for (let i = 0; i < buffer.length; i++) {
                const line = buffer.getLine(i)?.translateToString();
                if (line && line.includes('claude')) return true;
            }
            return false;
        }""",
        timeout=30_000,
    )

    # Skeleton — passos "type + assert task" ficam pra implementação
    # quando o E2E rodar host-side e o behavior real do Claude master
    # estiver verificado contra o stack completo (ai-jail + claude CLI).
