import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { connectWs } from './ws';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((ev: Event) => unknown) | null = null;
  onmessage: ((ev: MessageEvent) => unknown) | null = null;
  onclose: ((ev: CloseEvent) => unknown) | null = null;
  onerror: ((ev: Event) => unknown) | null = null;
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  close = vi.fn(() => {
    this.readyState = 3;
    this.onclose?.(new CloseEvent('close'));
  });
  send = vi.fn();
}

function instanceAt(index: number): MockWebSocket {
  const ws = MockWebSocket.instances[index];
  if (!ws) throw new Error(`no MockWebSocket at index ${index}`);
  return ws;
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('connectWs', () => {
  it('opens to /ws relative to current host', () => {
    connectWs(() => {});
    expect(instanceAt(0).url).toMatch(/\/ws$/);
  });

  it('forwards parsed JSON messages to onEvent', () => {
    const onEvent = vi.fn();
    connectWs(onEvent);
    const ws = instanceAt(0);
    ws.onmessage?.(new MessageEvent('message', {
      data: '{"type":"session.status","session_id":"x","payload":{},"at":"2026-05-09T00:00:00Z"}',
    }));
    expect(onEvent).toHaveBeenCalledOnce();
    expect(onEvent.mock.calls[0]?.[0].type).toBe('session.status');
  });

  it('ignores non-JSON messages', () => {
    const onEvent = vi.fn();
    connectWs(onEvent);
    const ws = instanceAt(0);
    ws.onmessage?.(new MessageEvent('message', { data: 'not-json' }));
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('reconnects with backoff after close', () => {
    connectWs(() => {});
    const first = instanceAt(0);
    first.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it('disconnect() stops reconnect loop', () => {
    const conn = connectWs(() => {});
    conn.disconnect();
    const first = instanceAt(0);
    first.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(5000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('disconnect after onclose schedules reconnect, but timer no-ops', () => {
    const conn = connectWs(() => {});
    const first = instanceAt(0);
    first.onclose?.(new CloseEvent('close'));
    conn.disconnect();
    vi.advanceTimersByTime(5000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('resets backoff on successful onopen', () => {
    connectWs(() => {});
    const first = instanceAt(0);
    first.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(1000);
    const second = instanceAt(1);
    second.onopen?.(new Event('open'));
    second.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it('calls onStateChange("connecting") before opening socket', () => {
    const onStateChange = vi.fn();
    connectWs(() => {}, onStateChange);
    expect(onStateChange).toHaveBeenCalledWith('connecting');
  });

  it('calls onStateChange("connected") on open', () => {
    const onStateChange = vi.fn();
    connectWs(() => {}, onStateChange);
    instanceAt(0).onopen?.(new Event('open'));
    expect(onStateChange).toHaveBeenCalledWith('connected');
  });

  it('calls onStateChange("reconnecting") on close when not stopped', () => {
    const onStateChange = vi.fn();
    connectWs(() => {}, onStateChange);
    instanceAt(0).onclose?.(new CloseEvent('close'));
    expect(onStateChange).toHaveBeenCalledWith('reconnecting');
  });

  it('calls onStateChange("offline") on close when stopped', () => {
    const onStateChange = vi.fn();
    const conn = connectWs(() => {}, onStateChange);
    conn.disconnect();
    instanceAt(0).onclose?.(new CloseEvent('close'));
    expect(onStateChange).toHaveBeenCalledWith('offline');
  });

  it('works without onStateChange (no crash)', () => {
    expect(() => {
      const conn = connectWs(() => {});
      instanceAt(0).onopen?.(new Event('open'));
      instanceAt(0).onclose?.(new CloseEvent('close'));
      conn.disconnect();
    }).not.toThrow();
  });
});
