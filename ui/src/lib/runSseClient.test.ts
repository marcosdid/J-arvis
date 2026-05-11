import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createLogsSse, type LogLine } from './runSseClient';

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

describe('createLogsSse', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens EventSource with encoded query params', () => {
    createLogsSse('r/1', 'svc x', vi.fn());
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]!.url).toBe(
      '/api/runs/r%2F1/logs?service=svc%20x',
    );
  });

  it('forwards parsed JSON lines to onLine', () => {
    const lines: LogLine[] = [];
    createLogsSse('r1', 'svc', (l) => lines.push(l));
    const es = FakeEventSource.instances[0]!;
    es.emit(JSON.stringify({ service: 'svc', stream: 'stdout', text: 'hi' }));
    es.emit(JSON.stringify({ service: 'svc', stream: 'stderr', text: 'warn' }));
    expect(lines).toEqual([
      { service: 'svc', stream: 'stdout', text: 'hi' },
      { service: 'svc', stream: 'stderr', text: 'warn' },
    ]);
  });

  it('silently ignores malformed lines', () => {
    const lines: LogLine[] = [];
    createLogsSse('r1', 'svc', (l) => lines.push(l));
    const es = FakeEventSource.instances[0]!;
    es.emit('not valid json {{{');
    expect(lines).toEqual([]);
  });

  it('forwards error events to onError when provided', () => {
    const onError = vi.fn();
    createLogsSse('r1', 'svc', vi.fn(), onError);
    FakeEventSource.instances[0]!.emitError();
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('does not crash when no onError handler is provided', () => {
    createLogsSse('r1', 'svc', vi.fn());
    // No throw: onerror is null, emitError uses optional chaining
    FakeEventSource.instances[0]!.emitError();
  });

  it('close() invokes EventSource.close', () => {
    const conn = createLogsSse('r1', 'svc', vi.fn());
    conn.close();
    expect(FakeEventSource.instances[0]!.closed).toBe(true);
  });
});
