import { render, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the Wails MasterAPI binding
const startMock = vi.fn();
const stopMock = vi.fn().mockResolvedValue(undefined);
const sendMock = vi.fn();
const resizeMock = vi.fn();
vi.mock('../../wailsjs/go/api/MasterAPI', () => ({
  Start: () => startMock(),
  Stop: () => stopMock(),
  Send: (data: string) => sendMock(data),
  Resize: (rows: number, cols: number) => resizeMock(rows, cols),
}));

// Mock the Wails event runtime so we can simulate master.exit
const eventHandlers: Record<string, ((payload: unknown) => void)[]> = {};
vi.mock('../../wailsjs/runtime/runtime', () => ({
  EventsOn: (name: string, fn: (payload: unknown) => void) => {
    eventHandlers[name] = eventHandlers[name] || [];
    eventHandlers[name].push(fn);
  },
  EventsOff: (name: string) => { delete eventHandlers[name]; },
}));

// Mock xterm so we don't need a real DOM terminal
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    write() {}
    open() {}
    onData() {}
    loadAddon() {}
    dispose() {}
    clear() {}
  },
}));
vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class { fit() {}; },
}));

import { MasterSidebar } from './MasterSidebar';

describe('MasterSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.keys(eventHandlers).forEach((k) => delete eventHandlers[k]);
  });

  it('auto-recovers on master.exit{early_exit:true}', async () => {
    startMock
      .mockResolvedValueOnce({ running: true, pid: 1, session_id: 'sess-1' })
      .mockResolvedValueOnce({ running: true, pid: 2, session_id: 'sess-2' });

    render(<MasterSidebar />);
    await waitFor(() => expect(startMock).toHaveBeenCalledTimes(1));

    // Simulate watchdog reporting early exit
    const handler = eventHandlers['master.exit']?.[0];
    expect(handler).toBeDefined();
    handler!({ early_exit: true, elapsed_ms: 1500, session_id: 'sess-1' });

    // Expect a second Start triggered by auto-recovery
    await waitFor(() => expect(startMock).toHaveBeenCalledTimes(2));
  });

  it('does not auto-recover on master.exit with early_exit:false', async () => {
    startMock.mockResolvedValue({ running: true, pid: 1, session_id: 'sess-1' });
    render(<MasterSidebar />);
    await waitFor(() => expect(startMock).toHaveBeenCalledTimes(1));

    const handler = eventHandlers['master.exit']?.[0];
    handler!({ early_exit: false, elapsed_ms: 60_000, session_id: 'sess-1' });

    // Give any pending async work a tick; assert no second Start
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(startMock).toHaveBeenCalledTimes(1);
  });
});
