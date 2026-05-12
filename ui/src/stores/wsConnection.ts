import { create } from 'zustand';

export type WsState = 'connecting' | 'connected' | 'reconnecting' | 'offline';

type Store = {
  state: WsState;
  setState: (s: WsState) => void;
};

export const useWsConnectionStore = create<Store>((set) => ({
  state: 'connecting',
  setState: (state) => set({ state }),
}));
