// F10 pivot: the UI no longer uses a real WebSocket. This module shims
// the legacy connectWs() API on top of Wails runtime events so existing
// consumers (useSessionEvents, ErrorBanner, StatusBar) keep working.

import { EventsOff, EventsOn } from '../wailsjs/runtime/runtime';

import type { WsEvent } from './events';
import type { WsState } from '../stores/wsConnection';

export type WsConnection = { disconnect: () => void };

type AnyPayload = Record<string, unknown> | unknown;

// All event names the Go bus may emit. Subscribing to ones not yet
// implemented is a no-op (no emitter exists yet).
const EVENT_NAMES = [
  'task.created',
  'task.updated',
  'task.discarded',
  'session.status',
  'session.tool_use',
  'session.stopped',
  'worktree.created',
  'worktree.removed',
  'worktree.orphaned',
  'run.status',
  'run.failed',
  'run.stopped',
  'bootstrap.proposed',
] as const;

function toIso(value: unknown): string {
  if (typeof value === 'string') return value;
  return new Date().toISOString();
}

function adaptEvent(name: string, payload: AnyPayload): WsEvent | null {
  const p = (payload ?? {}) as Record<string, unknown>;
  switch (name) {
    case 'task.created':
      return {
        type: 'task.created',
        session_id: '',
        task_id: String(p.id ?? ''),
        payload: {
          project_id: String(p.project_id ?? ''),
          title: String(p.title ?? ''),
          state: String(p.state ?? ''),
        },
        at: toIso(p.updated_at ?? p.created_at),
      };
    case 'task.updated':
      return {
        type: 'task.updated',
        session_id: '',
        task_id: String(p.id ?? ''),
        payload: {
          project_id: String(p.project_id ?? ''),
          title: String(p.title ?? ''),
          state: String(p.state ?? ''),
          previous_state: null,
        },
        at: toIso(p.updated_at),
      };
    case 'task.discarded':
      // Legacy event taxonomy folds discard into task.updated. The Go side
      // emits the full task object, so project_id/title are populated.
      return {
        type: 'task.updated',
        session_id: '',
        task_id: String(p.id ?? ''),
        payload: {
          project_id: String(p.project_id ?? ''),
          title: String(p.title ?? ''),
          state: 'discarded',
          previous_state: null,
        },
        at: toIso(p.updated_at),
      };
    default:
      // Other events (session.*, run.*, worktree.*, bootstrap.*) are not
      // yet emitted by the Go backend — they will be in F10.3+.
      return null;
  }
}

export function connectWs(
  onEvent: (event: WsEvent) => void,
  onStateChange?: (s: WsState) => void,
): WsConnection {
  // Wails events are in-process — no connection handshake. Mark connected
  // immediately and never reconnect.
  onStateChange?.('connected');

  EVENT_NAMES.forEach((name) => {
    EventsOn(name, (payload: AnyPayload) => {
      const ev = adaptEvent(name, payload);
      if (ev) onEvent(ev);
    });
  });

  return {
    disconnect: () => {
      EVENT_NAMES.forEach((name) => EventsOff(name));
      onStateChange?.('offline');
    },
  };
}
