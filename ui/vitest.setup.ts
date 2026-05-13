import '@testing-library/jest-dom';

// jsdom doesn't implement matchMedia; xterm.js (and other libs) probe it on
// construction. Provide a minimal no-op stub so terminal code can render in
// the test environment.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

// jsdom doesn't implement ResizeObserver; MasterSidebar uses it to refit the
// xterm terminal on container size changes. Tests don't exercise resize — a
// no-op stub is sufficient.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}
