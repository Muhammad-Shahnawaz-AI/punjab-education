import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OfficialCurriculumTools } from './OfficialCurriculumTools';

const apiMocks = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  importOfficialBook: vi.fn(),
  searchOfficialContent: vi.fn(),
}));

vi.mock('../lib/api', () => apiMocks);

describe('OfficialCurriculumTools', () => {
  beforeEach(() => {
    apiMocks.getCurrentUser.mockReset().mockResolvedValue({
      id: 1,
      email: 'admin@example.org',
      role: 'admin',
    });
    apiMocks.importOfficialBook.mockReset().mockResolvedValue({
      status: 'imported',
      book_id: 1,
      book: 'Mathematics 9',
      grade: 9,
      subject: 'Mathematics',
      chapters: 2,
      indexed_chunks: 12,
      page_count: 90,
      ocr_used: false,
      rights_basis: 'Open educational license',
      source_url: 'https://example.org/book.pdf',
    });
    apiMocks.searchOfficialContent.mockReset().mockResolvedValue([
      {
        book_id: 1,
        book: 'Mathematics 9',
        curriculum: 'Punjab Board',
        grade: 9,
        subject: 'Mathematics',
        chapter: 'Algebra',
        topic: 'Linear equations',
        page_number: 3,
        excerpt: 'A linear equation states that two expressions are equal.',
        source_name: 'Punjab Board',
        source_url: 'https://example.org/book.pdf',
        rights_basis: 'Open educational license',
      },
    ]);
  });

  it('searches approved excerpts and offers import to administrators', async () => {
    render(<OfficialCurriculumTools />);
    expect(await screen.findByRole('heading', { name: 'Import an approved textbook' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Textbook search'), {
      target: { value: 'linear equation' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText('A linear equation states that two expressions are equal.')).toBeInTheDocument();
    expect(apiMocks.searchOfficialContent).toHaveBeenCalledWith('linear equation');
  });

  it('submits an approved PDF with rights and outline metadata', async () => {
    render(<OfficialCurriculumTools />);
    const file = new File(['%PDF-sample'], 'math.pdf', { type: 'application/pdf' });
    fireEvent.change(await screen.findByLabelText('PDF textbook (maximum 50 MB)'), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Mathematics' } });
    fireEvent.change(screen.getByLabelText('Book title / edition'), {
      target: { value: 'Mathematics 9' },
    });
    fireEvent.change(screen.getByLabelText('Source name'), { target: { value: 'Punjab Board' } });
    fireEvent.change(screen.getByLabelText('HTTPS source URL'), {
      target: { value: 'https://example.org/book.pdf' },
    });
    fireEvent.change(screen.getByLabelText('Rights basis / permission record'), {
      target: { value: 'Open educational license verified' },
    });
    fireEvent.change(screen.getByLabelText(/Reviewed chapter outline/), {
      target: { value: '[{"name":"Algebra","start_page":1,"topics":["Equations"]}]' },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: /I confirm that permission/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Import and index PDF' }));

    await waitFor(() => expect(apiMocks.importOfficialBook).toHaveBeenCalledOnce());
    const submitted = apiMocks.importOfficialBook.mock.calls[0][0];
    expect(submitted.get('file')).toBe(file);
    expect(submitted.get('book_name')).toBe('Mathematics 9');
    expect(submitted.get('rights_confirmed')).toBe('true');
    expect(await screen.findByRole('status')).toHaveTextContent('12 searchable excerpts');
  });
});
