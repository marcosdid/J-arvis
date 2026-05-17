import { create } from 'zustand';

export type BootstrapProposedPayload = {
  task_id: string;
  manifest_text: string;
  valid: boolean;
  errors: string[];
};

type State = {
  last: BootstrapProposedPayload | null;
  // setLast MUST be called with a fresh object reference per emit (never
  // mutate the existing one in place). BootstrapModal's useEffect on the
  // `proposed` prop relies on reference identity to detect new emits and
  // re-trigger its state-machine transitions (invalid → valid, etc.).
  setLast: (p: BootstrapProposedPayload | null) => void;
};

export const useBootstrapProposedStore = create<State>((set) => ({
  last: null,
  setLast: (p) => set({ last: p }),
}));
