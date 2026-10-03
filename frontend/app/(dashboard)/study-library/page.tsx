'use client';

import {
  BookMarked,
  BookOpenCheck,
  Download,
  FileUp,
  LoaderCircle,
  MessageCircle,
  Send,
  Trash2,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import {
  askAboutBooks,
  deleteStudyBook,
  getStudyBookPdf,
  getStudyBooks,
  uploadStudyBook,
  type StudyBook,
  type StudyCitation,
} from '../../../lib/api';

type StudyMessage = {
  role: 'student' | 'assistant';
  content: string;
  citations?: StudyCitation[];
};

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export default function StudyLibraryPage() {
  const [books, setBooks] = useState<StudyBook[]>([]);
  const [selectedBookIds, setSelectedBookIds] = useState<number[]>([]);
  const [messages, setMessages] = useState<StudyMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState<'en' | 'ur'>('en');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [previewBook, setPreviewBook] = useState<StudyBook | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshBooks = useCallback(async () => {
    const nextBooks = await getStudyBooks();
    setBooks(nextBooks);
    setSelectedBookIds((current) => current.filter((id) => nextBooks.some((book) => book.id === id)));
    return nextBooks;
  }, []);

  useEffect(() => {
    let active = true;

    async function loadBooks() {
      try {
        const nextBooks = await getStudyBooks();
        if (active) setBooks(nextBooks);
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof Error ? loadError.message : 'Unable to load your study books.',
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }

    void loadBooks();
    return () => {
      active = false;
    };
  }, []);

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  function handleFileChange(file: File | null) {
    setUploadFile(file);
    setUploadTitle(file ? file.name.replace(/\.pdf$/i, '') : '');
    setError(null);
    setNotice(null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) {
      setError('Choose a PDF to upload.');
      return;
    }
    if (!uploadFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files can be added to your study library.');
      return;
    }
    if (uploadFile.size > MAX_UPLOAD_BYTES) {
      setError('Each PDF must be 20 MB or smaller.');
      return;
    }

    setIsUploading(true);
    setError(null);
    setNotice(null);
    try {
      const added = await uploadStudyBook(uploadFile, uploadTitle.trim());
      const nextBooks = await refreshBooks();
      setSelectedBookIds((current) => [...current, added.id]);
      setUploadFile(null);
      setUploadTitle('');
      setNotice(`${added.title} was added to your library.`);
      if (nextBooks.length === 1) setSelectedBookIds([added.id]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to upload this PDF.');
    } finally {
      setIsUploading(false);
    }
  }

  function toggleBook(bookId: number) {
    setError(null);
    setSelectedBookIds((current) => {
      if (current.includes(bookId)) return current.filter((id) => id !== bookId);
      if (current.length >= 3) {
        setError('Select up to three books for one study question.');
        return current;
      }
      return [...current, bookId];
    });
  }

  async function handlePreview(book: StudyBook) {
    setError(null);
    try {
      const pdf = await getStudyBookPdf(book.id);
      setPreviewUrl(URL.createObjectURL(pdf));
      setPreviewBook(book);
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : 'Unable to open this PDF.');
    }
  }

  async function handleDelete(book: StudyBook) {
    if (!window.confirm(`Remove “${book.title}” and its extracted text from your library?`)) return;

    setError(null);
    setNotice(null);
    try {
      await deleteStudyBook(book.id);
      setBooks((current) => current.filter((item) => item.id !== book.id));
      setSelectedBookIds((current) => current.filter((id) => id !== book.id));
      setMessages([]);
      if (previewBook?.id === book.id) {
        setPreviewBook(null);
        setPreviewUrl(null);
      }
      setNotice(`${book.title} was removed.`);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to remove this book.');
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = prompt.trim();
    if (selectedBookIds.length === 0) {
      setError('Select at least one book before asking a study question.');
      return;
    }
    if (!question) return;

    setIsAsking(true);
    setError(null);
    setNotice(null);
    try {
      const response = await askAboutBooks(selectedBookIds, question, language);
      setMessages((current) => [
        ...current,
        { role: 'student', content: question },
        { role: 'assistant', content: response.answer, citations: response.citations },
      ]);
      setPrompt('');
    } catch (askError) {
      setError(askError instanceof Error ? askError.message : 'Study AI could not answer right now.');
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Personal learning space
        </p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">My study books</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Keep your PDFs in a private library and ask study questions answered from the selected
          books, with page references.
        </p>
      </div>

      {error ? (
        <div role="alert" className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div role="status" className="mb-5 rounded-2xl bg-emerald-50 p-3 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      <div className="grid items-start gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-5">
          <form
            onSubmit={(event) => void handleUpload(event)}
            className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--lav)] text-slate-800">
                <FileUp size={18} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Add a book</h2>
                <p className="text-xs text-slate-500">PDF format · up to 20 MB · selectable text</p>
              </div>
            </div>

            <label className="mt-5 block text-sm font-medium text-slate-700">
              Choose a PDF
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => handleFileChange(event.currentTarget.files?.[0] ?? null)}
                className="mt-2 block w-full rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm file:mr-3 file:rounded-xl file:border-0 file:bg-white file:px-3 file:py-2 file:font-semibold"
              />
            </label>
            <label className="mt-4 block text-sm font-medium text-slate-700">
              Book title
              <input
                value={uploadTitle}
                onChange={(event) => setUploadTitle(event.target.value)}
                maxLength={240}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
                placeholder="e.g. Grade 12 Biology"
              />
            </label>
            <button
              type="submit"
              disabled={isUploading || !uploadFile}
              className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-[var(--lav)] px-4 py-2.5 text-sm font-semibold text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? <LoaderCircle size={16} className="animate-spin" /> : <FileUp size={16} />}
              {isUploading ? 'Reading and saving…' : 'Upload to my library'}
            </button>
          </form>

          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--mint)] text-slate-800">
                  <BookMarked size={18} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Your library</h2>
                  <p className="text-xs text-slate-500">Private to your account</p>
                </div>
              </div>
              {selectedBookIds.length > 0 ? (
                <span className="text-xs font-medium text-slate-500">
                  {selectedBookIds.length}/3 selected
                </span>
              ) : null}
            </div>

            {isLoading ? (
              <p className="mt-5 inline-flex items-center gap-2 text-sm text-slate-500">
                <LoaderCircle size={15} className="animate-spin" /> Loading your books…
              </p>
            ) : books.length === 0 ? (
              <div className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                Your library is empty. Add a text-based PDF to start asking questions about it.
              </div>
            ) : (
              <ul className="mt-5 space-y-3">
                {books.map((book) => {
                  const selected = selectedBookIds.includes(book.id);
                  return (
                    <li
                      key={book.id}
                      className={`rounded-2xl border p-3 transition ${
                        selected ? 'border-slate-900 bg-slate-50' : 'border-slate-200'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          aria-label={`Use ${book.title} for study chat`}
                          checked={selected}
                          onChange={() => toggleBook(book.id)}
                          className="mt-1 h-4 w-4 accent-slate-900"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold text-slate-900">{book.title}</div>
                          <div className="mt-1 text-xs text-slate-500">
                            {book.page_count} pages · {(book.file_size / (1024 * 1024)).toFixed(1)} MB
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => void handlePreview(book)}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm"
                            >
                              <Download size={13} /> Open PDF
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDelete(book)}
                              className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50"
                            >
                              <Trash2 size={13} /> Remove
                            </button>
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <section className="overflow-hidden rounded-[28px] bg-white shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center gap-3 border-b border-slate-100 p-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--yellow)] text-slate-800">
              <MessageCircle size={18} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Ask about your books</h2>
              <p className="text-xs text-slate-500">Answers use excerpts from the selected PDFs</p>
            </div>
          </div>

          <div className="flex min-h-[360px] flex-col gap-4 p-5">
            {messages.length === 0 ? (
              <div className="m-auto max-w-sm text-center">
                <BookOpenCheck className="mx-auto text-slate-400" size={28} />
                <p className="mt-3 font-semibold text-slate-800">Your study chat starts here</p>
                <p className="mt-1 text-sm text-slate-500">
                  Select one or more books, then ask for explanations, summaries, practice, or help
                  understanding a concept.
                </p>
              </div>
            ) : (
              messages.map((message, index) => (
                <article
                  key={`${message.role}-${index}`}
                  dir={message.role === 'assistant' && language === 'ur' ? 'rtl' : undefined}
                  className={`max-w-[92%] rounded-2xl p-4 text-sm leading-6 ${
                    message.role === 'student'
                      ? 'ml-auto bg-[var(--lav)] text-slate-900'
                      : 'mr-auto bg-slate-50 text-slate-800'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.citations?.length ? (
                    <div className="mt-3 border-t border-slate-200 pt-2 text-xs text-slate-500">
                      Sources: {message.citations.map((citation) => `${citation.book_title}, p. ${citation.page_number}`).join(' · ')}
                    </div>
                  ) : null}
                </article>
              ))
            )}
          </div>

          <form onSubmit={(event) => void handleAsk(event)} className="border-t border-slate-100 p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <label className="text-xs font-medium text-slate-600" htmlFor="study-language">
                Answer language
              </label>
              <select
                id="study-language"
                value={language}
                onChange={(event) => setLanguage(event.target.value as 'en' | 'ur')}
                className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm"
              >
                <option value="en">English</option>
                <option value="ur">Urdu</option>
              </select>
            </div>
            <label className="sr-only" htmlFor="study-prompt">Your study question</label>
            <textarea
              id="study-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={2000}
              rows={3}
              dir={language === 'ur' ? 'rtl' : 'auto'}
              placeholder="Ask for an explanation, a chapter summary, practice questions, or help with a concept…"
              className="w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm outline-none focus:border-slate-400"
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-xs text-slate-500">
                {selectedBookIds.length ? `${selectedBookIds.length} book${selectedBookIds.length === 1 ? '' : 's'} selected` : 'Select books from your library first.'}
              </p>
              <button
                type="submit"
                disabled={isAsking || selectedBookIds.length === 0 || !prompt.trim()}
                className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isAsking ? <LoaderCircle size={15} className="animate-spin" /> : <Send size={15} />}
                {isAsking ? 'Thinking…' : 'Ask AI'}
              </button>
            </div>
          </form>
        </section>
      </div>

      {previewUrl && previewBook ? (
        <div className="fixed inset-0 z-50 flex flex-col bg-slate-950/80 p-3 sm:p-6">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between rounded-t-2xl bg-white px-4 py-3">
            <span className="truncate font-semibold text-slate-900">{previewBook.title}</span>
            <button
              type="button"
              aria-label="Close PDF preview"
              onClick={() => {
                setPreviewBook(null);
                setPreviewUrl(null);
              }}
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            >
              <X size={20} />
            </button>
          </div>
          <iframe
            title={`${previewBook.title} PDF`}
            src={previewUrl}
            className="mx-auto min-h-0 w-full max-w-5xl flex-1 rounded-b-2xl bg-white"
          />
        </div>
      ) : null}
    </section>
  );
}
