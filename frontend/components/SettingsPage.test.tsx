import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from '../app/(dashboard)/settings/page';

const apiMocks = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getUserSettings: vi.fn(),
  updateUserSettings: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  getCurrentUser: apiMocks.getCurrentUser,
  getUserSettings: apiMocks.getUserSettings,
  updateUserSettings: apiMocks.updateUserSettings,
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    apiMocks.getCurrentUser.mockReset().mockResolvedValue({
      id: 1,
      email: 'teacher@example.com',
      role: 'teacher',
      settings: {},
    });
    apiMocks.getUserSettings.mockReset().mockResolvedValue({
      full_name: 'Sana Ali',
      email: 'teacher@example.com',
      department: 'Science',
      phone: '+92 300 1234567',
      interface_language: 'English',
      time_zone: 'Asia/Karachi',
      date_format: 'DD/MM/YYYY',
      notifications: {
        weekly_curriculum_summaries: true,
        assessment_reminders: true,
        ai_generated_content_alerts: false,
      },
    });
    apiMocks.updateUserSettings.mockReset().mockResolvedValue({
      full_name: 'Sana Ali',
      email: 'teacher@example.com',
      department: 'Science',
      phone: '+92 300 1234567',
      interface_language: 'English',
      time_zone: 'Asia/Karachi',
      date_format: 'DD/MM/YYYY',
      notifications: {
        weekly_curriculum_summaries: true,
        assessment_reminders: true,
        ai_generated_content_alerts: false,
      },
    });
  });

  it('renders the profile and language settings sections', async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: /workspace settings/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /profile details/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /language preferences/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
  });
});
