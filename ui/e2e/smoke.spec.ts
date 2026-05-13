import { test, expect } from '@playwright/test';
import { openApp, initGitFixture } from './helpers';

test('app loads — kanban shell renders, header shows "+ new task"', async ({ page }) => {
  await openApp(page);
  // The "+ new task" button proves the header + app shell mounted.
  await expect(page.getByRole('button', { name: /new task/i })).toBeVisible({ timeout: 10_000 });
});

test('create a project via drawer, then create a task on kanban', async ({ page }) => {
  await openApp(page);

  // Open Projects drawer via the "[p] projects" button in the header.
  await page.getByRole('button', { name: /projects/i }).first().click();

  // Fill the create-project form.
  const name = `e2e-project-${Date.now()}`;
  const path = await initGitFixture({ name });
  await page.getByLabel('project-name').fill(name);
  await page.getByLabel('project-path').fill(path);
  await page.getByRole('form', { name: 'add-project' }).getByRole('button').click();

  // Project should appear in the list (filter to this run's name).
  await expect(page.locator('section.project-node').filter({ hasText: name })).toBeVisible({ timeout: 5_000 });

  // Close drawer (Escape works on Radix sheets reliably).
  await page.keyboard.press('Escape');

  // Open new-task sheet via the "+ new task" button in the header.
  await page.getByRole('button', { name: /new task/i }).click();

  // Find the new-task form (the sheet appears as a Radix Dialog with
  // aria-label="new-task").
  const form = page.getByRole('dialog').filter({ hasText: /new task|nova tarefa/i }).first();
  await expect(form).toBeVisible({ timeout: 5_000 });

  // Title input has aria-label="título" (component is pt-BR).
  await page.getByLabel('título').fill('e2e first task');
  await page.getByRole('button', { name: 'Criar' }).click();

  // Verify it landed in the kanban.
  await expect(page.getByText('e2e first task')).toBeVisible({ timeout: 5_000 });
});
