import { unlinkSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT_FILE = join(__dirname, '.e2e-port');

export default async function globalTeardown(): Promise<void> {
  const proc = globalThis.__jarvisE2EProcess;
  if (proc && !proc.killed) {
    console.log('[e2e] killing jarvis-e2e binary');
    proc.kill('SIGTERM');
  }
  if (existsSync(PORT_FILE)) {
    unlinkSync(PORT_FILE);
  }
}
