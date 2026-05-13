import { test, expect } from '@playwright/test';
import { openApp, initGitFixture, gitWorktreeAdd, e2ePort } from './helpers';

test.describe('projects + worktrees flow', () => {
  test('create monorepo: project has one repository', async ({ page }) => {
    await openApp(page);
    const fixture = `monorepo-${Date.now()}`;
    const path = await initGitFixture({ name: fixture });
    await page.getByRole('button', { name: /projects/i }).first().click();
    const name = `mono-${Date.now()}`;
    await page.getByLabel('project-name').fill(name);
    await page.getByLabel('project-path').fill(path);
    await page.getByRole('form', { name: 'add-project' }).getByRole('button').click();
    const project = page.locator('section.project-node').filter({ hasText: name });
    await expect(project).toBeVisible({ timeout: 5_000 });
  });

  test('create multi-repo: project lists N repositories', async ({ page }) => {
    await openApp(page);
    const fixture = `multi-${Date.now()}`;
    const path = await initGitFixture({
      name: fixture,
      subDirs: ['zeta', 'alpha', 'mango'],
    });
    await page.getByRole('button', { name: /projects/i }).first().click();
    const name = `multi-${Date.now()}`;
    await page.getByLabel('project-name').fill(name);
    await page.getByLabel('project-path').fill(path);
    await page.getByRole('form', { name: 'add-project' }).getByRole('button').click();
    const project = page.locator('section.project-node').filter({ hasText: name });
    await expect(project).toBeVisible({ timeout: 5_000 });
  });

  test('create project at no-git path is rejected', async ({ page }) => {
    await openApp(page);
    const bogus = '/tmp/jarvis-e2e-nonexistent-' + Date.now();
    await page.getByRole('button', { name: /projects/i }).first().click();
    const name = `reject-${Date.now()}`;
    await page.getByLabel('project-name').fill(name);
    await page.getByLabel('project-path').fill(bogus);
    await page.getByRole('form', { name: 'add-project' }).getByRole('button').click();
    await expect(page.locator('section.project-node').filter({ hasText: name })).toHaveCount(0, { timeout: 3_000 });
  });

  test('listWorktrees via API after gitWorktreeAdd discovers orphan', async ({ page }) => {
    await openApp(page);
    const repoPath = await initGitFixture({ name: `orphan-${Date.now()}` });
    const port = e2ePort();

    const createRes = await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
      data: { name: `orphan-${Date.now()}`, path: repoPath },
    });
    expect(createRes.ok()).toBeTruthy();
    const project = await createRes.json();

    const wtPath = `/tmp/jarvis-wt-${Date.now()}`;
    await gitWorktreeAdd(repoPath, wtPath, 'feature/orphan');

    const listRes = await page.request.post(`http://127.0.0.1:${port}/e2e/worktrees/list_by_project`, {
      data: { project_id: project.id },
    });
    expect(listRes.ok()).toBeTruthy();
    const worktrees = await listRes.json();
    const found = worktrees.find((w: any) => w.path === wtPath);
    expect(found).toBeTruthy();
    expect(found.branch).toBe('feature/orphan');
    expect(found.is_orphan).toBe(true);
  });

  test('discard task end-to-end (cleanup hook wired)', async ({ page }) => {
    await openApp(page);
    const repoPath = await initGitFixture({ name: `cleanup-${Date.now()}` });
    const port = e2ePort();

    const project = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: `proj-${Date.now()}`, path: repoPath },
      })
    ).json();
    const task = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
        data: { project_id: project.id, title: 'cleanup-task' },
      })
    ).json();

    const res = await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/discard`, {
      data: { id: task.id },
    });
    expect(res.status()).toBe(204);

    const after = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/get`, { data: { id: task.id } })
    ).json();
    expect(after.state).toBe('discarded');
  });
});
