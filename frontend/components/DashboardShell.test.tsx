import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DashboardShell } from './DashboardShell';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));

describe('DashboardShell', () => {
  it('renders workspace links as real routes', () => {
    render(
      <DashboardShell>
        <div>Overview content</div>
      </DashboardShell>,
    );

    expect(screen.getByRole('link', { name: /curriculum/i })).toHaveAttribute(
      'href',
      '/curriculum',
    );
    expect(screen.getByRole('link', { name: /analytics/i })).toHaveAttribute(
      'href',
      '/analytics',
    );
    expect(screen.getByText('Overview content')).toBeInTheDocument();
  });

  it('marks the current route in navigation', () => {
    render(<DashboardShell><div /></DashboardShell>);

    expect(screen.getByRole('link', { name: /overview/i })).toHaveAttribute('aria-current', 'page');
  });
});