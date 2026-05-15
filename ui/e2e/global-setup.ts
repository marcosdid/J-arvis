import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

declare global {
  // eslint-disable-next-line no-var
  var __jarvisE2EProcess: ChildProcessWithoutNullStreams | undefined;
  // eslint-disable-next-line no-var
  var __jarvisE2EPort: number | undefined;
}

const BINARY = join(__dirname, '..', '..', 'build', 'bin', 'jarvis-e2e-http');
const PORT_FILE = join(__dirname, '.e2e-port');

export default async function globalSetup(): Promise<void> {
  const tmp = mkdtempSync(join(tmpdir(), 'jarvis-e2e-'));
  const dbPath = join(tmp, 'jarvis.db');

  console.log(`[e2e] spawning ${BINARY} (db=${dbPath})`);

  const proc = spawn(BINARY, [], {
    env: {
      ...process.env,
      JARVIS_DB_PATH: dbPath,
      // Avoid opening a real window during E2E — the binary still tries
      // to but on a headless CI this matters less. On a dev machine,
      // the window opens briefly. (No way to suppress it short of a
      // separate cmd/jarvis-e2e-only-http build, which is overkill for now.)
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  globalThis.__jarvisE2EProcess = proc;

  const port = await new Promise<number>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('e2e binary never printed E2E_HTTP_PORT')), 15_000);
    proc.stdout.on('data', (chunk: Buffer) => {
      const text = chunk.toString();
      process.stdout.write(`[jarvis-e2e] ${text}`);
      const m = text.match(/E2E_HTTP_PORT=(\d+)/);
      if (m) {
        clearTimeout(timeout);
        resolve(Number(m[1]));
      }
    });
    proc.stderr.on('data', (chunk: Buffer) => {
      process.stderr.write(`[jarvis-e2e err] ${chunk.toString()}`);
    });
    proc.on('exit', (code) => {
      clearTimeout(timeout);
      reject(new Error(`e2e binary exited early with code ${code}`));
    });
  });

  globalThis.__jarvisE2EPort = port;
  writeFileSync(PORT_FILE, String(port));
  console.log(`[e2e] binary up, HTTP port=${port}`);
}
