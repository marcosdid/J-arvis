import { test, expect, type Page } from '@playwright/test';

import { openApp, e2ePort, initGitFixture } from './helpers';

// Run from Panel. Needs docker (available) — NOT ai-jail (worktrees are created
// via git only). Setup uses the /e2e fixtures (create-worktree + write-manifest).
// RUN-01 is driven through the UI to prove the e2e-shim runs wiring end-to-end
// (RunsBinding -> /e2e/runs/*); the guards are asserted at the API level.

const MANIFEST_OK = `version: "1"
services:
  cache:
    image: redis:7
`;

async function seed(page: Page, port: number, prefix: string) {
  const path = await initGitFixture({ name: `${prefix}-${Date.now()}` });
  const project = await (
    await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
      data: { name: `${prefix}-${Date.now()}`, path },
    })
  ).json();
  const task = await (
    await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
      data: { project_id: project.id, title: `${prefix}-task` },
    })
  ).json();
  return { project, task };
}

async function makeWorktreeWithManifest(page: Page, port: number, taskId: string, branch: string) {
  const wts = await (
    await page.request.post(`http://127.0.0.1:${port}/e2e/fixtures/create-worktree`, {
      data: { task_id: taskId, branch },
    })
  ).json();
  await page.request.post(`http://127.0.0.1:${port}/e2e/fixtures/write-manifest`, {
    data: { cwd: wts[0].path, yaml: MANIFEST_OK },
  });
  return wts[0].path as string;
}

function cardFor(page: Page, title: string) {
  return page.locator('[data-card-state]').filter({ hasText: title });
}

test.describe('run from panel', () => {
  // RUN-01 + RUN-17 — driven through the UI via the detail sheet "run" tab.
  // Proves the e2e-shim runs wiring end-to-end (RunsBinding.Start/Get -> /e2e/runs/*).
  // (The card-embedded ▶ Run only renders for in_progress/review tasks; the run
  // tab is the state-independent entry point.)
  test('start a run from the detail run tab to ready, then stop (UI)', async ({ page }) => {
    test.setTimeout(60_000);
    await openApp(page);
    const port = e2ePort();
    const { task } = await seed(page, port, 'run-ready');
    await makeWorktreeWithManifest(page, port, task.id, 'run/ready');
    await page.reload();

    await cardFor(page, 'run-ready-task')
      .getByRole('heading', { name: 'run-ready-task' })
      .click();
    const sheet = page.getByRole('dialog');
    await expect(sheet).toBeVisible({ timeout: 5_000 });
    await sheet.getByRole('tab', { name: 'run' }).click();

    await sheet.getByRole('button', { name: 'run-tab-start' }).click();
    // reaching "ready" swaps the ▶ Run button for the Stop control
    await expect(sheet.getByRole('button', { name: 'run-tab-stop' })).toBeVisible({ timeout: 40_000 });

    await sheet.getByRole('button', { name: 'run-tab-stop' }).click();
    await expect(sheet.getByRole('button', { name: 'run-tab-stop' })).toHaveCount(0, { timeout: 15_000 });
  });

  // RUN-02 — no manifest → bootstrap hint (no docker, no ai-jail).
  test('starting a run with no manifest returns a bootstrap hint', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const { task } = await seed(page, port, 'run-nomanifest');
    // worktree exists (cwd) but no manifest written
    await page.request.post(`http://127.0.0.1:${port}/e2e/fixtures/create-worktree`, {
      data: { task_id: task.id, branch: 'run/no-manifest' },
    });
    const res = await page.request.post(`http://127.0.0.1:${port}/e2e/runs/start`, {
      data: { task_id: task.id },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.bootstrap?.reason).toBe('manifest_missing');
    expect(body.run).toBeFalsy();
  });

  // RUN-22 — terminal task is not eligible to run.
  test('starting a run on a terminal (discarded) task is rejected', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const { task } = await seed(page, port, 'run-terminal');
    await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/discard`, {
      data: { id: task.id },
    });
    const res = await page.request.post(`http://127.0.0.1:${port}/e2e/runs/start`, {
      data: { task_id: task.id },
    });
    expect(res.ok()).toBeFalsy();
  });

  // RUN-23 — second start while a run is active is rejected.
  test('second start while a run is active is rejected', async ({ page }) => {
    test.setTimeout(60_000);
    await openApp(page);
    const port = e2ePort();
    const { task } = await seed(page, port, 'run-active');
    await makeWorktreeWithManifest(page, port, task.id, 'run/active');

    const first = await page.request.post(`http://127.0.0.1:${port}/e2e/runs/start`, {
      data: { task_id: task.id },
    });
    expect(first.ok()).toBeTruthy();
    const firstBody = await first.json();
    expect(firstBody.run?.status).toBe('ready');

    const second = await page.request.post(`http://127.0.0.1:${port}/e2e/runs/start`, {
      data: { task_id: task.id },
    });
    expect(second.ok()).toBeFalsy();

    await page.request.post(`http://127.0.0.1:${port}/e2e/runs/stop`, {
      data: { run_id: firstBody.run.id },
    });
  });
});
