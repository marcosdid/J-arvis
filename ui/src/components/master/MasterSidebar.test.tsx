import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MasterSidebar } from './MasterSidebar';

vi.mock('@xterm/xterm', () => ({
  Terminal: vi.fn().mockImplementation(() => ({
    loadAddon: vi.fn(),
    open: vi.fn(),
    onData: vi.fn(),
    onResize: vi.fn(),
    write: vi.fn(),
    dispose: vi.fn(),
  })),
}));

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: vi.fn().mockImplementation(() => ({
    fit: vi.fn(),
  })),
}));

class MockWebSocket {
  static OPEN = 1;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  readyState = 0;
  url: string;
  sentMessages: string[] = [];
  private _listeners: Map<string, Set<EventListener>> = new Map();

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = 1;
      this.onopen?.(new Event('open'));
    }, 0);
  }
  send(data: string) {
    this.sentMessages.push(data);
  }
  close() {}
  addEventListener(type: string, listener: EventListener) {
    if (!this._listeners.has(type)) this._listeners.set(type, new Set());
    this._listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: EventListener) {
    this._listeners.get(type)?.delete(listener);
  }
}

describe('MasterSidebar', () => {
  let originalWs: typeof WebSocket;
  let wsInstance: MockWebSocket | null;

  beforeEach(() => {
    wsInstance = null;
    originalWs = globalThis.WebSocket;
    // @ts-expect-error mock
    globalThis.WebSocket = class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        wsInstance = this as unknown as MockWebSocket;
      }
    };
  });

  afterEach(() => {
    globalThis.WebSocket = originalWs;
  });

  it('renders sidebar with header', () => {
    render(<MasterSidebar />);
    expect(screen.getByLabelText('master-session')).toBeInTheDocument();
    expect(screen.getByText('master_001')).toBeInTheDocument();
  });

  it('opens WebSocket to /ws/master', async () => {
    render(<MasterSidebar />);
    await new Promise((r) => setTimeout(r, 10));
    expect(wsInstance).not.toBeNull();
    expect(wsInstance!.url).toMatch(/\/ws\/master$/);
  });

  it('renders system error banner when WS sends type=system level=error', async () => {
    render(<MasterSidebar />);
    await new Promise((r) => setTimeout(r, 10));
    expect(wsInstance).not.toBeNull();
    await act(async () => {
      wsInstance!.onmessage?.(
        new MessageEvent('message', {
          data: JSON.stringify({
            type: 'system',
            level: 'error',
            message: 'master session not available',
          }),
        }),
      );
    });
    const banner = await screen.findByLabelText('system-msg');
    expect(banner).toHaveTextContent('master session not available');
    expect(banner.className).toContain('error');
  });
});
