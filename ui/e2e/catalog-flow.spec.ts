import { test, expect, type Page } from '@playwright/test';

import { openApp, initGitFixture } from './helpers';

// Catalog templates/profiles — now testable e2e because the catalog is wired
// into the shim (/e2e/catalog/get). Previously harness-blocked.

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
  await page.keyboard.press('Escape');
}

test.describe('catalog templates', () => {
  // CAT-02 — the template dropdown is populated from the catalog.
  test('new-task template dropdown is populated from the catalog', async ({ page }) => {
    await openApp(page);
    await createProjectViaUI(page, `cat-${Date.now()}`);

    await page.getByRole('button', { name: /new task/i }).click();
    const values = await page
      .getByLabel('template')
      .locator('option')
      .evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
    expect(values).toContain('frontend');
    expect(values).toContain('backend');
  });

  // CAT-09 — a task created with a template shows the template badge on the card.
  test('a task created with a template shows the template badge', async ({ page }) => {
    await openApp(page);
    await createProjectViaUI(page, `cat-${Date.now()}`);

    await page.getByRole('button', { name: /new task/i }).click();
    await page.getByLabel('título').fill('templated task');
    await page.getByLabel('template').selectOption('frontend');
    await page.getByRole('button', { name: 'Criar' }).click();

    const card = page.locator('[data-card-state]').filter({ hasText: 'templated task' });
    await expect(card.getByTestId('template-badge')).toBeVisible({ timeout: 5_000 });
    await expect(card.getByTestId('template-badge')).toContainText(/frontend/i);
  });
});
