import { beforeEach, describe, expect, it } from 'vitest';
import { useWsConnectionStore, type WsState } from './wsConnection';

function resetStore() {
  useWsConnectionStore.setState({ state: 'connecting' });
}

beforeEach(resetStore);

describe('useWsConnectionStore', () => {
  it('initial state is connecting', () => {
    expect(useWsConnectionStore.getState().state).toBe('connecting');
  });

  it('setState transitions to connected', () => {
    useWsConnectionStore.getState().setState('connected');
    expect(useWsConnectionStore.getState().state).toBe('connected');
  });

  it('setState transitions to reconnecting', () => {
    useWsConnectionStore.getState().setState('reconnecting');
    expect(useWsConnectionStore.getState().state).toBe('reconnecting');
  });

  it('setState transitions to offline', () => {
    useWsConnectionStore.getState().setState('offline');
    expect(useWsConnectionStore.getState().state).toBe('offline');
  });

  it('setState is stable across calls', () => {
    const { setState } = useWsConnectionStore.getState();
    const states: WsState[] = ['connected', 'reconnecting', 'offline', 'connecting'];
    for (const s of states) {
      setState(s);
      expect(useWsConnectionStore.getState().state).toBe(s);
    }
  });
});
