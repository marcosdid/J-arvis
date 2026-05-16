import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createLogsSse, type LogLine } from './runSseClient';

vi.mock('./api', () => ({
  api: {
    getRunLogsEventSourceURL: vi.fn(),
  },
}));

import { api } from './api';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  emit(data: string): void {
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  emitError(): void {
    this.onerror?.(new Event('error'));
  }

  close(): void {
    this.closed = true;
  }
}

// Helper: flush pending microtasks so the awaited URL resolves and the
// FakeEventSource is constructed before assertions.
const flush = () => new Promise<void>((r) => setTimeout(r, 0));

describe('createLogsSse', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
    (api.getRunLogsEventSourceURL as ReturnType<typeof vi.fn>).mockImplementation(
      (runId: string, service: string) =>
        Promise.resolve(
          `http://127.0.0.1:9999/api/runs/${encodeURIComponent(runId)}/logs?service=${encodeURIComponent(service)}`,
        ),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('opens EventSource with URL resolved by api.getRunLogsEventSourceURL', async () => {
    createLogsSse('r/1', 'svc x', vi.fn());
    await flush();
    expect(api.getRunLogsEventSourceURL).toHaveBeenCalledWith('r/1', 'svc x');
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]!.url).toBe(
      'http://127.0.0.1:9999/api/runs/r%2F1/logs?service=svc%20x',
    );
  });

  it('forwards parsed JSON lines to onLine', async () => {
    const lines: LogLine[] = [];
    createLogsSse('r1', 'svc', (l) => lines.push(l));
    await flush();
    const es = FakeEventSource.instances[0]!;
    es.emit(JSON.stringify({ service: 'svc', stream: 'stdout', text: 'hi' }));
    es.emit(JSON.stringify({ service: 'svc', stream: 'stderr', text: 'warn' }));
    expect(lines).toEqual([
      { service: 'svc', stream: 'stdout', text: 'hi' },
      { service: 'svc', stream: 'stderr', text: 'warn' },
    ]);
  });

  it('silently ignores malformed lines', async () => {
    const lines: LogLine[] = [];
    createLogsSse('r1', 'svc', (l) => lines.push(l));
    await flush();
    const es = FakeEventSource.instances[0]!;
    es.emit('not valid json {{{');
    expect(lines).toEqual([]);
  });

  it('forwards error events to onError when provided', async () => {
    const onError = vi.fn();
    createLogsSse('r1', 'svc', vi.fn(), onError);
    await flush();
    FakeEventSource.instances[0]!.emitError();
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('does not crash when no onError handler is provided', async () => {
    createLogsSse('r1', 'svc', vi.fn());
    await flush();
    // No throw: onerror is null, emitError uses optional chaining
    FakeEventSource.instances[0]!.emitError();
  });

  it('close() invokes EventSource.close after URL resolves', async () => {
    const conn = createLogsSse('r1', 'svc', vi.fn());
    await flush();
    conn.close();
    expect(FakeEventSource.instances[0]!.closed).toBe(true);
  });

  it('close() before URL resolves prevents EventSource construction', async () => {
    const conn = createLogsSse('r1', 'svc', vi.fn());
    // Fechado ANTES do microtask resolver — guard `closed` evita construir es.
    conn.close();
    await flush();
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
