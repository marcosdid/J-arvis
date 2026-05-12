import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocketRTT } from './useWebSocketRTT';

class FakeWS {
  readyState = WebSocket.OPEN;
  sent: string[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  send(s: string) { this.sent.push(s); }
  close() {}
  addEventListener(event: string, handler: (ev: MessageEvent) => void) {
    if (event === 'message') this.onmessage = handler;
  }
  removeEventListener() { /* noop */ }
}

describe('useWebSocketRTT', () => {
  it('records RTT after pong', async () => {
    vi.useFakeTimers();
    const ws = new FakeWS();
    const { result } = renderHook(() => useWebSocketRTT(ws as unknown as WebSocket));
    await act(async () => { vi.advanceTimersByTime(1000); });
    const sent = JSON.parse(ws.sent[0]);
    expect(sent.type).toBe('ping');
    await act(async () => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'pong', ts: sent.ts }) } as MessageEvent);
    });
    expect(result.current).toBeGreaterThanOrEqual(0);
    vi.useRealTimers();
  });

  it('returns null when ws is null', () => {
    const { result } = renderHook(() => useWebSocketRTT(null));
    expect(result.current).toBeNull();
  });

  it('ignores malformed JSON messages', async () => {
    vi.useFakeTimers();
    const ws = new FakeWS();
    const { result } = renderHook(() => useWebSocketRTT(ws as unknown as WebSocket));
    await act(async () => { vi.advanceTimersByTime(1000); });
    await act(async () => {
      ws.onmessage?.({ data: 'not-valid-json' } as MessageEvent);
    });
    expect(result.current).toBeNull();
    vi.useRealTimers();
  });

  it('ignores pong with mismatched ts', async () => {
    vi.useFakeTimers();
    const ws = new FakeWS();
    const { result } = renderHook(() => useWebSocketRTT(ws as unknown as WebSocket));
    await act(async () => { vi.advanceTimersByTime(1000); });
    await act(async () => {
      // Send a pong with a different ts than what was sent
      ws.onmessage?.({ data: JSON.stringify({ type: 'pong', ts: 9999999 }) } as MessageEvent);
    });
    expect(result.current).toBeNull();
    vi.useRealTimers();
  });

  it('does not send ping when readyState is not OPEN', async () => {
    vi.useFakeTimers();
    const ws = new FakeWS();
    ws.readyState = WebSocket.CLOSED;
    renderHook(() => useWebSocketRTT(ws as unknown as WebSocket));
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(ws.sent).toHaveLength(0);
    vi.useRealTimers();
  });
});
