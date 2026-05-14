import { test, expect } from '@playwright/test';

import { openApp, e2ePort, initGitFixture, simulateHook, getSessionToken } from './helpers';

test.describe('sessions flow', () => {
  test('start session button disabled when sandbox unavailable', async ({ page }) => {
    // Runs against an e2e-http instance started with JARVIS_E2E_NO_SANDBOX=1,
    // which fakes sandbox_available=false. No harness sets that today, so this
    // test self-skips until one does.
    test.skip(!process.env.JARVIS_E2E_NO_SANDBOX, 'requires no-sandbox harness');
    await openApp(page);
    const port = e2ePort();
    const proj = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: 'p1', path: await initGitFixture({ name: 'no-sandbox-fix' }) },
      })
    ).json();
    await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
      data: { project_id: proj.id, title: 'unsandboxed-task' },
    });
    await page.reload();
    const btn = page.getByTestId('task-session-start').first();
    await expect(btn).toBeVisible();
    await expect(btn).toBeDisabled();
  });

  test('start session creates session and opens panel', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const path = await initGitFixture({ name: `sess-start-${Date.now()}` });
    const proj = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: `proj-${Date.now()}`, path },
      })
    ).json();
    await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
      data: { project_id: proj.id, title: 'sess-task' },
    });
    await page.reload();
    const btn = page.getByTestId('task-session-start').first();
    await btn.click();
    // Panel opens (Sheet has role=dialog).
    await expect(page.getByText('Sessões').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('session-status-chip').first()).toContainText(
      /executing|awaiting_response/,
      { timeout: 5_000 },
    );
  });

  test('simulated hook drives status_changed live in UI', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const path = await initGitFixture({ name: `sim-hook-${Date.now()}` });
    const proj = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: `proj-${Date.now()}`, path },
      })
    ).json();
    const task = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
        data: { project_id: proj.id, title: 'hook-task' },
      })
    ).json();
    const sess = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/sessions/start`, {
        data: { task_id: task.id },
      })
    ).json();
    const token = await getSessionToken(sess.id);

    await simulateHook(token, 'Notification', { message: 'user needed' });

    await page.reload(); // shim doesn't push events; reload reads fresh DB
    const chip = page.getByTestId('session-status-chip').first();
    await expect(chip).toContainText('awaiting_response', { timeout: 5_000 });
  });

  test('stop closes session; status becomes done', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const path = await initGitFixture({ name: `stop-${Date.now()}` });
    const proj = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: `proj-${Date.now()}`, path },
      })
    ).json();
    const task = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
        data: { project_id: proj.id, title: 'stop-task' },
      })
    ).json();
    const sess = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/sessions/start`, {
        data: { task_id: task.id },
      })
    ).json();
    const stopRes = await page.request.post(`http://127.0.0.1:${port}/e2e/sessions/stop`, {
      data: { id: sess.id },
    });
    expect(stopRes.status()).toBe(204);

    const after = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/sessions/list_by_task`, {
        data: { task_id: task.id },
      })
    ).json();
    const found = after.find((s: { id: string }) => s.id === sess.id);
    expect(found.status).toBe('done');
    expect(found.ended_at).not.toBeNull();
  });
});
