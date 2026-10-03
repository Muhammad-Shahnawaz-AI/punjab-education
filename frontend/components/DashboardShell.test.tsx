import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AuthUser } from '../lib/api';
import { DashboardShell } from './DashboardShell';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));
const teacher: AuthUser = { id: 2, email: 'teacher@example.com', role: 'teacher' };

describe('DashboardShell', () => {
  it('renders workspace links as real routes', () => {
    render(
      <DashboardShell user={teacher} onLogout={() => {}}>
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
    render(<DashboardShell user={teacher} onLogout={() => {}}><div /></DashboardShell>);

    expect(screen.getByRole('link', { name: /overview/i })).toHaveAttribute('aria-current', 'page');
  });

  it('limits student navigation to student routes', () => {
    render(
      <DashboardShell user={{ ...teacher, role: 'student' }} onLogout={() => {}}>
        <div />
      </DashboardShell>,
    );

    expect(screen.getByRole('link', { name: /curriculum/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /my study books/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /analytics/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /user management/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /let's create/i })).not.toBeInTheDocument();
  });
});