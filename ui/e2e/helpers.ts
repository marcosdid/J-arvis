import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Page } from '@playwright/test';

const __dirname = dirname(fileURLToPath(import.meta.url));

export function e2ePort(): number {
  const raw = readFileSync(join(__dirname, '.e2e-port'), 'utf-8').trim();
  return Number(raw);
}

export async function openApp(page: Page, path = '/'): Promise<void> {
  const port = e2ePort();
  // Forward console errors to the test runner stdout — invaluable for
  // diagnosing UI breakage.
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.error(`[browser console error] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    console.error(`[browser pageerror] ${err.message}`);
  });
  await page.goto(`${path}?e2e=1&e2ePort=${port}`);
}
