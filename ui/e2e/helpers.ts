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

export async function initGitFixture(opts: { name: string; subDirs?: string[] }): Promise<string> {
  const port = e2ePort();
  const res = await fetch(`http://127.0.0.1:${port}/e2e/fixtures/init-git`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: opts.name, sub_dirs: opts.subDirs }),
  });
  if (!res.ok) throw new Error(`init-git failed: ${await res.text()}`);
  const { path } = await res.json();
  return path;
}

export async function gitWorktreeAdd(repoPath: string, targetPath: string, branch: string): Promise<void> {
  const port = e2ePort();
  const res = await fetch(`http://127.0.0.1:${port}/e2e/fixtures/git-worktree-add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_path: repoPath, target_path: targetPath, branch }),
  });
  if (!res.ok) throw new Error(`git worktree add failed: ${await res.text()}`);
}
