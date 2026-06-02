import { test, expect, type Page } from '@playwright/test';

import { openApp, e2ePort, initGitFixture } from './helpers';

// TaskDetailSheet + TaskCard badges. Setup seeds a project+task via the e2e
// HTTP API (fast/deterministic), then reloads so the card renders.

async function seedTask(page: Page, title: string): Promise<void> {
  const port = e2ePort();
  const path = await initGitFixture({ name: `detail-${Date.now()}` });
  const project = await (
    await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
      data: { name: `detail-${Date.now()}`, path },
    })
  ).json();
  await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
    data: { project_id: project.id, title },
  });
  await page.reload();
}

function cardFor(page: Page, title: string) {
  return page.locator('[data-card-state]').filter({ hasText: title });
}

test.describe('task detail + card', () => {
  test('clicking a card opens the detail sheet with overview/sessions/run/logs tabs', async ({ page }) => {
    await openApp(page);
    await seedTask(page, 'detail task');

    const card = cardFor(page, 'detail task');
    await expect(card).toBeVisible({ timeout: 5_000 });
    await card.getByRole('heading', { name: 'detail task' }).click();

    const sheet = page.getByRole('dialog');
    await expect(sheet).toBeVisible({ timeout: 5_000 });
    for (const tab of ['overview', 'sessions', 'run', 'logs']) {
      await expect(sheet.getByRole('tab', { name: tab })).toBeVisible();
    }
  });

  // NOTE: the "run" tab content is NOT asserted here — the runs subsystem has
  // no e2e HTTP route (RunsBinding.Get throws under e2e), so the tab stays in a
  // retrying/loading state. RunTab/RunStatus are unit-covered. We assert tab
  // switching against the static LogsTab placeholder instead.
  test('detail tab switching renders tab content (logs placeholder)', async ({ page }) => {
    await openApp(page);
    await seedTask(page, 'tabswitch task');

    await cardFor(page, 'tabswitch task').getByRole('heading', { name: 'tabswitch task' }).click();
    const sheet = page.getByRole('dialog');
    await expect(sheet).toBeVisible({ timeout: 5_000 });

    await sheet.getByRole('tab', { name: 'logs' }).click();
    await expect(sheet.getByText(/coming soon|streaming/i)).toBeVisible({ timeout: 5_000 });
  });

  test('task card shows the permission profile badge (yolo by default)', async ({ page }) => {
    await openApp(page);
    await seedTask(page, 'badge task');

    const badge = cardFor(page, 'badge task').getByTestId('profile-badge');
    await expect(badge).toBeVisible({ timeout: 5_000 });
    await expect(badge).toContainText(/yolo/i);
  });
});
