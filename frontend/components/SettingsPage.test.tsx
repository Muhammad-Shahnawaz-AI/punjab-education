import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SettingsPage from '../app/(dashboard)/settings/page';

describe('SettingsPage', () => {
  it('renders the profile and language settings sections', () => {
    render(<SettingsPage />);

    expect(screen.getByRole('heading', { name: /workspace settings/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /profile details/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /language preferences/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
  });
});
