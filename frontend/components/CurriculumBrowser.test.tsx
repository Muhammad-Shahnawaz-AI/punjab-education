import '@testing-library/jest-dom/vitest';
import { QueryProvider } from './QueryProvider';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../lib/api';
import { CurriculumBrowser } from './CurriculumBrowser';

vi.mock('../lib/api', () => ({
  getBooks: vi.fn(),
  getChapters: vi.fn(),
  getCurricula: vi.fn(),
  getGrades: vi.fn(),
  getSubjects: vi.fn(),
  getTopics: vi.fn(),
}));

describe('CurriculumBrowser', () => {
  beforeEach(() => {
    vi.mocked(api.getCurricula).mockResolvedValue({
      curricula: [
        {
          id: 'sample-placeholder',
          name: 'Sample Curriculum (Placeholder)',
          description: 'Sample only, not official curriculum.',
          is_sample: true,
        },
      ],
    });
    vi.mocked(api.getGrades).mockResolvedValue({ items: [{ id: 9, name: 'Grade 9' }] });
    vi.mocked(api.getSubjects).mockResolvedValue({ items: [{ id: 12, name: 'Sample Subject' }] });
    vi.mocked(api.getBooks).mockResolvedValue({ items: [{ id: 4, name: 'Sample Book' }] });
    vi.mocked(api.getChapters).mockResolvedValue({ items: [{ id: 5, name: 'Sample Chapter' }] });
    vi.mocked(api.getTopics).mockResolvedValue({ items: [{ id: 6, name: 'Sample Topic' }] });
  });

  it('loads each catalog level from the selected parent', async () => {
    render(
      <QueryProvider>
        <CurriculumBrowser />
      </QueryProvider>,
    );

    await screen.findByRole('option', { name: 'Sample Curriculum (Placeholder)' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Curriculum' }), {
      target: { value: 'sample-placeholder' },
    });
    await screen.findByRole('option', { name: 'Grade 9' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Grade' }), {
      target: { value: '9' },
    });
    await screen.findByRole('option', { name: 'Sample Subject' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Subject' }), {
      target: { value: '12' },
    });
    await screen.findByRole('option', { name: 'Sample Book' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Book' }), {
      target: { value: '4' },
    });
    await screen.findByRole('option', { name: 'Sample Chapter' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Chapter' }), {
      target: { value: '5' },
    });

    expect(await screen.findByRole('option', { name: 'Sample Topic' })).toBeInTheDocument();
    expect(screen.getByText(/not official curriculum/i)).toBeInTheDocument();
    expect(api.getTopics).toHaveBeenCalledWith(5);
  });

  it('shows an empty state when the API has no curricula', async () => {
    vi.mocked(api.getCurricula).mockResolvedValue({ curricula: [] });

    render(
      <QueryProvider>
        <CurriculumBrowser />
      </QueryProvider>,
    );

    expect(await screen.findByText('No curriculum available.')).toBeInTheDocument();
  });
});