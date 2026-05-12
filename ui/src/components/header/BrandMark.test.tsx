import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BrandMark } from './BrandMark';

describe('BrandMark', () => {
  it('renders the text j-arvis', () => {
    render(<BrandMark />);
    expect(screen.getByText(/j-arvis/i)).toBeInTheDocument();
  });

  it('has aria-label "J-arvis brand" accessible name', () => {
    render(<BrandMark />);
    expect(
      screen.getByRole('generic', { name: 'J-arvis brand' }),
    ).toBeInTheDocument();
  });

  it('has text-accent-primary class on the brand text', () => {
    const { container } = render(<BrandMark />);
    const span = container.querySelector('.text-accent-primary');
    expect(span).not.toBeNull();
  });
});
