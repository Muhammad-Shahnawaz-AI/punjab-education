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
  getCurriculumStudyBooks,
  getStudyBookPdf,
  getStudyBooks,
  uploadStudyBook,
  type StudyBook,
  type StudyCitation,
  type CurriculumStudyBook,
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
  const [curriculumBooks, setCurriculumBooks] = useState<CurriculumStudyBook[]>([]);
  const [selectedCurriculumBookIds, setSelectedCurriculumBookIds] = useState<number[]>([]);
  const [messages, setMessages] = useState<StudyMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState<'en' | 'ur'>('en');
  const [selectedSubject, setSelectedSubject] = useState('General Education');
  const [selectedIntent, setSelectedIntent] = useState('explain');
  const [selectedGrade, setSelectedGrade] = useState('General');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [imageData, setImageData] = useState<string | null>(null);
  const [imageName, setImageName] = useState('');
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

  useEffect(() => {
    let active = true;
    void getCurriculumStudyBooks()
      .then((readyBooks) => {
        if (active) setCurriculumBooks(readyBooks);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Unable to load shared curriculum books.',
          );
        }
      });
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

  function handleImageChange(file: File | null) {
    if (!file) {
      setImageData(null);
      setImageName('');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setImageData(typeof reader.result === 'string' ? reader.result : null);
      setImageName(file.name);
    };
    reader.readAsDataURL(file);
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
      await refreshBooks();
      setSelectedBookIds((current) =>
        current.length + selectedCurriculumBookIds.length < 3
          ? [...current, added.id]
          : current,
      );
      setUploadFile(null);
      setUploadTitle('');
      setNotice(`${added.title} was added to your library.`);
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
      if (current.length + selectedCurriculumBookIds.length >= 3) {
        setError('Select up to three books for one study question.');
        return current;
      }
      return [...current, bookId];
    });
  }

  function toggleCurriculumBook(bookId: number) {
    setError(null);
    setSelectedCurriculumBookIds((current) => {
      if (current.includes(bookId)) return current.filter((id) => id !== bookId);
      if (current.length + selectedBookIds.length >= 3) {
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
    if (!question) return;

    setIsAsking(true);
    setError(null);
    setNotice(null);
    try {
      const response = await askAboutBooks(
        selectedBookIds,
        question,
        language,
        imageData,
        selectedSubject,
        selectedIntent,
        selectedGrade,
        selectedCurriculumBookIds,
      );
      setMessages((current) => [
        ...current,
        { role: 'student', content: question },
        { role: 'assistant', content: response.answer, citations: response.citations },
      ]);
      setPrompt('');
      setImageData(null);
      setImageName('');
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
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                No books have been added to the portal yet. The admin has not uploaded any books here yet, and the AI can only answer education-related questions and general learning support for this platform.
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
                <p className="mt-3 font-semibold text-slate-800">Education assistant</p>
                <p className="mt-1 text-sm text-slate-500">
                  {books.length === 0
                    ? 'No books have been added by the admin yet. You can still ask education-related questions about the platform, learning topics, or school subjects.'
                    : 'Select one or more books, then ask for explanations, summaries, practice, or help understanding a concept.'}
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
            <div className="mb-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-600">
                Subject
                <select
                  value={selectedSubject}
                  onChange={(event) => setSelectedSubject(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="General Education">General Education</option>
                  <option value="Mathematics">Mathematics</option>
                  <option value="Science">Science</option>
                  <option value="English">English</option>
                  <option value="Computer Science">Computer Science</option>
                  <option value="Social Studies">Social Studies</option>
                </select>
              </label>

              <label className="text-xs font-medium text-slate-600">
                Task type
                <select
                  value={selectedIntent}
                  onChange={(event) => setSelectedIntent(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="explain">Explain concept</option>
                  <option value="summary">Summarize chapter</option>
                  <option value="quiz">Practice questions</option>
                  <option value="solve">Solve problem</option>
                </select>
              </label>

              <label className="text-xs font-medium text-slate-600">
                Grade / class
                <select
                  value={selectedGrade}
                  onChange={(event) => setSelectedGrade(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="General">General</option>
                  <option value="Grade 6">Grade 6</option>
                  <option value="Grade 7">Grade 7</option>
                  <option value="Grade 8">Grade 8</option>
                  <option value="Grade 9">Grade 9</option>
                  <option value="Grade 10">Grade 10</option>
                  <option value="Grade 11">Grade 11</option>
                  <option value="Grade 12">Grade 12</option>
                </select>
              </label>

              <label className="text-xs font-medium text-slate-600" htmlFor="study-language">
                Answer language
                <select
                  id="study-language"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as 'en' | 'ur')}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="en">English</option>
                  <option value="ur">Urdu</option>
                </select>
              </label>
            </div>

            <label className="mb-3 flex cursor-pointer items-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              <FileUp size={15} />
              <span>{imageName ? imageName : 'Attach an image (optional)'}</span>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => handleImageChange(event.currentTarget.files?.[0] ?? null)}
                className="hidden"
              />
            </label>

            <label className="sr-only" htmlFor="study-prompt">Your study question</label>
            <textarea
              id="study-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={2000}
              rows={3}
              dir={language === 'ur' ? 'rtl' : 'auto'}
              placeholder="Write the learning question here…"
              className="w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm outline-none focus:border-slate-400"
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-xs text-slate-500">
                {selectedBookIds.length ? `${selectedBookIds.length} book${selectedBookIds.length === 1 ? '' : 's'} selected` : 'No books added by admin yet; platform-only educational help is available.'}
              </p>
              <button
                type="submit"
                disabled={isAsking || !prompt.trim()}
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
