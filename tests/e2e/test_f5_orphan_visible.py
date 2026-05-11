"""F5 E2E: externally-created worktree shows up as órfã and is removable.

⚠️ Cannot run from inside ai-jail (gotcha #9). User runs manually from host:
    uv run pytest tests/e2e/test_f5_orphan_visible.py -v

Flow:
1. Fixture pre-creates a monorepo at /tmp/repos/withorphan and an external
   worktree at /tmp/repos/withorphan-external (via `git worktree add ...`
   from outside the daemon).
2. Add project via drawer → daemon syncs and detects the external worktree
   as órfã (task_id NULL).
3. Drawer shows "órfãs (1)" group with the external branch.
4. Click ✕ on the orphan → row disappears.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f5_external_worktree_visible_as_orphan_and_removable(
    page: Page, orchestrator_with_external_worktree: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_external_worktree

    page.goto(url)

    page.get_by_role("button", name="Projetos ▾").click()
    expect(page.locator('[role="dialog"][aria-label="projects-drawer"]')).to_be_visible()
    page.get_by_label("project-name").fill("withorphan")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.locator(".project-node strong", has_text="withorphan")).to_be_visible()

    # `git worktree list` returns both the primary checkout (branch=main) and
    # the externally-created one (branch=external). Neither has task_id, so
    # both become órfãs after sync.
    orphans_group = page.locator(".orphans-group")
    expect(orphans_group).to_be_visible()
    expect(orphans_group.locator(".orphans-label")).to_have_text("órfãs (2)")

    orphan_rows = orphans_group.locator(".wt-row")
    expect(orphan_rows).to_have_count(2)

    external_row = orphan_rows.filter(has=page.locator(".branch", has_text="external"))
    expect(external_row).to_have_count(1)
    external_row.locator('button[aria-label^="remove-worktree-"]').click()
    expect(orphans_group.locator(".wt-row")).to_have_count(1)
