import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudyLibraryPage from '../app/(dashboard)/study-library/page';

const apiMocks = vi.hoisted(() => ({
  askAboutBooks: vi.fn(),
  deleteStudyBook: vi.fn(),
  getStudyBookPdf: vi.fn(),
  getStudyBooks: vi.fn(),
  uploadStudyBook: vi.fn(),
}));

vi.mock('../lib/api', () => apiMocks);

const book = {
  id: 12,
  title: 'Grade 12 Biology',
  filename: 'biology.pdf',
  file_size: 4096,
  page_count: 20,
  created_at: '2026-10-03T00:00:00Z',
};

describe('StudyLibraryPage', () => {
  beforeEach(() => {
    apiMocks.getStudyBooks.mockReset().mockResolvedValue([book]);
    apiMocks.askAboutBooks.mockReset().mockResolvedValue({
      answer: 'Photosynthesis transforms light energy into chemical energy.',
      citations: [{ book_id: 12, book_title: book.title, page_number: 4 }],
    });
    apiMocks.deleteStudyBook.mockReset().mockResolvedValue({ status: 'deleted' });
    apiMocks.getStudyBookPdf.mockReset().mockResolvedValue(new Blob(['%PDF-test']));
    apiMocks.uploadStudyBook.mockReset().mockResolvedValue({ ...book, id: 13 });
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  it('loads a user book and asks an Urdu question grounded in it', async () => {
    render(<StudyLibraryPage />);

    const selector = await screen.findByRole('checkbox', {
      name: `Use ${book.title} for study chat`,
    });
    fireEvent.click(selector);
    fireEvent.change(screen.getByLabelText('Your study question'), {
      target: { value: 'Explain photosynthesis' },
    });
    fireEvent.change(screen.getByLabelText('Answer language'), {
      target: { value: 'ur' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }));

    await waitFor(() => {
      expect(apiMocks.askAboutBooks).toHaveBeenCalledWith(
        [book.id],
        'Explain photosynthesis',
        'ur',
        null,
        'General Education',
        'explain',
        'General',
      );
    });
    expect(
      await screen.findByText('Photosynthesis transforms light energy into chemical energy.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Grade 12 Biology, p\. 4/)).toBeInTheDocument();
  });

  it('uploads a PDF to the signed-in user library', async () => {
    render(<StudyLibraryPage />);
    await screen.findByRole('checkbox', { name: `Use ${book.title} for study chat` });
    const file = new File(['%PDF-sample'], 'chemistry.pdf', { type: 'application/pdf' });

    fireEvent.change(screen.getByLabelText('Choose a PDF'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Upload to my library' }));

    await waitFor(() => {
      expect(apiMocks.uploadStudyBook).toHaveBeenCalledWith(file, 'chemistry');
    });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Grade 12 Biology was added to your library.',
    );
  });
});
