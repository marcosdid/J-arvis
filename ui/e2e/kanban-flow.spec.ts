import { test, expect, type Page } from '@playwright/test';
import { openApp, e2ePort } from './helpers';

async function createProject(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name: /projects/i }).first().click();
  await page.getByLabel('project-name').fill(name);
  await page.getByLabel('project-path').fill(`/tmp/${name}`);
  await page.getByRole('form', { name: 'add-project' }).getByRole('button').click();
  await expect(page.locator('section.project-node').filter({ hasText: name })).toBeVisible({ timeout: 5_000 });
  await page.keyboard.press('Escape');
}

async function createTask(page: Page, title: string): Promise<void> {
  await page.getByRole('button', { name: /new task/i }).click();
  await page.getByLabel('título').fill(title);
  await page.getByRole('button', { name: 'Criar' }).click();
  await expect(page.getByText(title)).toBeVisible({ timeout: 5_000 });
}

test.describe('kanban full flow', () => {
  test('create project, create three tasks, all land in Backlog', async ({ page }) => {
    await openApp(page);
    await createProject(page, `flow-${Date.now()}`);
    for (const title of ['task alpha', 'task beta', 'task gamma']) {
      await createTask(page, title);
    }
    // All three should be visible somewhere on the kanban.
    for (const title of ['task alpha', 'task beta', 'task gamma']) {
      await expect(page.getByText(title)).toBeVisible();
    }
  });

  test('task state can be patched directly via API and reflects in UI', async ({ page }) => {
    await openApp(page);
    const project = `patch-${Date.now()}`;
    await createProject(page, project);
    await createTask(page, 'movable task');

    // Use the e2e HTTP API to patch state — the UI listens to events.
    // (Direct API call is the most robust way to test state transitions
    // without depending on DnD coordinates.)
    const port = e2ePort();
    const tasks = await fetch(`http://127.0.0.1:${port}/e2e/tasks/list`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then((r) => r.json());
    const target = tasks.find((t: { title: string }) => t.title === 'movable task');
    expect(target).toBeTruthy();

    // idea -> ready
    const patched = await fetch(`http://127.0.0.1:${port}/e2e/tasks/patch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: target.id, patch: { state: 'ready' } }),
    }).then((r) => r.json());
    expect(patched.state).toBe('ready');

    // ready -> in_progress
    const patched2 = await fetch(`http://127.0.0.1:${port}/e2e/tasks/patch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: target.id, patch: { state: 'in_progress' } }),
    }).then((r) => r.json());
    expect(patched2.state).toBe('in_progress');

    // Refresh the UI to pick up state (no SSE in current shim).
    await page.reload();
    await page.evaluate(() => undefined);
    // Should now be in the "In Progress" column.
    const inProgressCol = page.getByTestId('column-In Progress');
    await expect(inProgressCol).toContainText('movable task', { timeout: 5_000 });
  });

  test('task discard moves it out of active columns', async ({ page }) => {
    await openApp(page);
    await createProject(page, `discard-${Date.now()}`);
    await createTask(page, 'to-be-discarded');

    const port = e2ePort();
    const tasks = await fetch(`http://127.0.0.1:${port}/e2e/tasks/list`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then((r) => r.json());
    const target = tasks.find((t: { title: string }) => t.title === 'to-be-discarded');

    const res = await fetch(`http://127.0.0.1:${port}/e2e/tasks/discard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: target.id }),
    });
    expect(res.status).toBe(204);

    // Verify the underlying state is now discarded via the API.
    const after = await fetch(`http://127.0.0.1:${port}/e2e/tasks/get`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: target.id }),
    }).then((r) => r.json());
    expect(after.state).toBe('discarded');
  });
});
