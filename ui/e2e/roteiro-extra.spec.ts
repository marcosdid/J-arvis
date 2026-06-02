import { test, expect, type Page } from '@playwright/test';

import { openApp, e2ePort, initGitFixture } from './helpers';

// Next batch of roteiro cases not covered by the original 4 specs:
// header counts, project delete (ok + blocked-with-tasks), keyboard
// shortcuts, and the template badge on a task card.

async function createProjectViaUI(page: Page, name: string): Promise<void> {
  const path = await initGitFixture({ name });
  await page.getByRole('button', { name: /projects/i }).first().click();
  await page.getByLabel('project-name').fill(name);
  await page.getByLabel('project-path', { exact: true }).fill(path);
  await page
    .getByRole('form', { name: 'add-project' })
    .getByRole('button', { name: 'Adicionar projeto' })
    .click();
  await expect(
    page.locator('section.project-node').filter({ hasText: name }),
  ).toBeVisible({ timeout: 5_000 });
}

test.describe('roteiro extra — projects/header/shortcuts/catalog', () => {
  // PRJ-14
  test('header reflects project and task counts', async ({ page }) => {
    await openApp(page);
    await expect(page.getByText(/0 proj·0 tsk/)).toBeVisible();

    const name = `count-${Date.now()}`;
    await createProjectViaUI(page, name);
    await expect(page.getByText(/1 proj·0 tsk/)).toBeVisible({ timeout: 5_000 });

    await page.keyboard.press('Escape'); // close drawer
    await page.getByRole('button', { name: /new task/i }).click();
    await page.getByLabel('título').fill('count task');
    await page.getByRole('button', { name: 'Criar' }).click();
    await expect(page.getByText(/1 proj·1 tsk/)).toBeVisible({ timeout: 5_000 });
  });

  // PRJ-07
  test('delete project with no tasks removes it', async ({ page }) => {
    await openApp(page);
    const name = `del-${Date.now()}`;
    await createProjectViaUI(page, name);

    await page.getByRole('button', { name: `delete-${name}` }).click();
    await expect(
      page.locator('section.project-node').filter({ hasText: name }),
    ).toHaveCount(0, { timeout: 5_000 });
  });

  // PRJ-08
  test('delete project with tasks is rejected', async ({ page }) => {
    await openApp(page);
    const port = e2ePort();
    const path = await initGitFixture({ name: `delblock-${Date.now()}` });
    const project = await (
      await page.request.post(`http://127.0.0.1:${port}/e2e/projects/create`, {
        data: { name: `delblock-${Date.now()}`, path },
      })
    ).json();
    await page.request.post(`http://127.0.0.1:${port}/e2e/tasks/create`, {
      data: { project_id: project.id, title: 'blocks-delete' },
    });

    const res = await page.request.post(
      `http://127.0.0.1:${port}/e2e/projects/delete`,
      { data: { id: project.id } },
    );
    expect(res.ok()).toBeFalsy(); // has tasks -> must refuse
  });

  // UI-45
  test('[n] shortcut opens the new-task sheet', async ({ page }) => {
    await openApp(page);
    await page.keyboard.press('n');
    await expect(
      page.getByRole('dialog').filter({ hasText: /new task|nova tarefa/i }).first(),
    ).toBeVisible({ timeout: 5_000 });
  });

  // UI-44
  test('[p] shortcut opens the projects drawer', async ({ page }) => {
    await openApp(page);
    await page.keyboard.press('p');
    await expect(
      page.getByRole('dialog').filter({ hasText: /Projetos|Worktrees/i }).first(),
    ).toBeVisible({ timeout: 5_000 });
  });

  // NOTE: CAT-09/TSK-21 (template badge on card) intentionally NOT covered here.
  // The catalog is not served by the e2e HTTP shim (api.ts stubs getCatalog in
  // e2e mode), so the template dropdown is empty under e2e. Template selection
  // and payload are already covered by NewTaskSheet.test.tsx unit tests. Wiring
  // a /e2e/catalog route would unblock an e2e version if ever needed.
});
