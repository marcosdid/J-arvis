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
