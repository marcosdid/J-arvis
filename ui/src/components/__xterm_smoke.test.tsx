import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StrictMode } from 'react';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

describe('xterm.js compat smoke', () => {
  it('Terminal constructs + opens in jsdom without throwing', () => {
    const Container = () => {
      const div = document.createElement('div');
      document.body.appendChild(div);
      const term = new Terminal({ rows: 24, cols: 80 });
      term.open(div);
      term.dispose();
      return null;
    };
    expect(() => {
      render(<StrictMode><Container /></StrictMode>);
    }).not.toThrow();
  });
});
