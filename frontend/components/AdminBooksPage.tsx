"use client";

import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CloudUpload,
  FileText,
  Pause,
  Play,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelAdminBookUpload,
  deleteAdminBook,
  getAdminBookUploadPolicy,
  getAdminBooks,
  getCurricula,
  getGrades,
  getSubjects,
  retryAdminBookProcessing,
  uploadAdminBook,
  type AdminBook,
  type AdminBookUploadMetadata,
  type AdminBookUploadPolicy,
  type CatalogItem,
  type Curriculum,
} from "../lib/api";

type UploadState =
  | "queued"
  | "uploading"
  | "paused"
  | "processing"
  | "ready"
  | "processingFailed"
  | "failed"
  | "cancelled";

type QueuedPdf = {
  id: string;
  file: File;
  title: string;
  state: UploadState;
  loaded: number;
  startedAt?: number;
  sessionId?: string;
  bookId?: number;
  error?: string;
};

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400";
const buttonClass =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50";

export default function AdminBooksPage() {
  const [policy, setPolicy] = useState<AdminBookUploadPolicy | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [grades, setGrades] = useState<CatalogItem[]>([]);
  const [subjects, setSubjects] = useState<CatalogItem[]>([]);
  const [curriculumCode, setCurriculumCode] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [author, setAuthor] = useState("");
  const [language, setLanguage] = useState("English");
  const [edition, setEdition] = useState("");
  const [description, setDescription] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [rightsBasis, setRightsBasis] = useState("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [useOcr, setUseOcr] = useState(false);
  const [ocrLanguage, setOcrLanguage] = useState<"eng" | "urd" | "eng+urd">("eng");
  const [queue, setQueue] = useState<QueuedPdf[]>([]);
  const [books, setBooks] = useState<AdminBook[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyBooks, setBusyBooks] = useState<number[]>([]);
  const controllers = useRef(new Map<string, AbortController>());
  const fileInput = useRef<HTMLInputElement>(null);

  const refreshBooks = useCallback(async () => {
    const response = await getAdminBooks(offset);
    setBooks(response);
  }, [offset]);

  useEffect(() => {
    let active = true;
    void Promise.all([getAdminBookUploadPolicy(), getCurricula()])
      .then(([uploadPolicy, catalog]) => {
        if (!active) return;
        setPolicy(uploadPolicy);
        setCurricula(catalog.curricula);
        setCurriculumCode(catalog.curricula[0]?.id ?? "");
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load the book-upload configuration.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (!curriculumCode) {
      setGrades([]);
      setGradeId("");
      return;
    }
    void getGrades(curriculumCode)
      .then((response) => {
        if (!active) return;
        setGrades(response.items);
        setGradeId(response.items[0] ? String(response.items[0].id) : "");
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load grades.");
      });
    return () => {
      active = false;
    };
  }, [curriculumCode]);

  useEffect(() => {
    let active = true;
    if (!gradeId) {
      setSubjects([]);
      setSubjectId("");
      return;
    }
    void getSubjects(Number(gradeId))
      .then((response) => {
        if (!active) return;
        setSubjects(response.items);
        setSubjectId(response.items[0] ? String(response.items[0].id) : "");
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load subjects.");
      });
    return () => {
      active = false;
    };
  }, [gradeId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void refreshBooks()
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load books.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refreshBooks]);

  useEffect(() => {
    if (!books.some((book) => book.processing_status === "queued" || book.processing_status === "processing")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshBooks().catch((loadError: unknown) => {
        setError(loadError instanceof Error ? loadError.message : "Unable to refresh processing status.");
      });
    }, 4000);
    return () => window.clearInterval(timer);
  }, [books, refreshBooks]);

  useEffect(() => {
    setQueue((previous) =>
      previous.map((item) => {
        if (item.bookId === undefined) return item;
        const book = books.find((entry) => entry.book_id === item.bookId);
        if (!book) return item;
        return {
          ...item,
          state:
            book.processing_status === "ready"
              ? "ready"
              : book.processing_status === "failed"
                ? "processingFailed"
                : "processing",
          error: book.last_error ?? undefined,
        };
      }),
    );
  }, [books]);

  async function addFiles(files: FileList | File[]) {
    setError(null);
    const accepted: QueuedPdf[] = [];
    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError(`${file.name}: only PDF files are accepted.`);
        continue;
      }
      if (file.size < 5) {
        setError(`${file.name}: the file is empty or too small to be a PDF.`);
        continue;
      }
      let signature: string;
      try {
        signature = await readSignature(file);
      } catch {
        setError(`${file.name}: the browser could not read the PDF header.`);
        continue;
      }
      if (signature !== "%PDF-") {
        setError(`${file.name}: the file does not have a PDF signature.`);
        continue;
      }
      if (policy && file.size > policy.max_size_bytes) {
        setError(
          `${file.name}: this exceeds the configured ${formatBytes(policy.max_size_bytes)} size limit.`,
        );
        continue;
      }
      accepted.push({
        id: crypto.randomUUID(),
        file,
        title: file.name.replace(/\.pdf$/i, "").slice(0, 200),
        state: "queued",
        loaded: 0,
      });
    }
    setQueue((previous) => [...previous, ...accepted]);
  }

  function metadataFor(item: QueuedPdf): AdminBookUploadMetadata {
    return {
      title: item.title.trim(),
      author: author.trim() || undefined,
      grade_id: Number(gradeId),
      subject_id: Number(subjectId),
      source_name: sourceName.trim(),
      source_url: sourceUrl.trim(),
      rights_basis: rightsBasis.trim(),
      rights_confirmed: rightsConfirmed,
      language: language.trim(),
      edition: edition.trim() || undefined,
      description: description.trim() || undefined,
      use_ocr: useOcr,
      ocr_language: ocrLanguage,
    };
  }

  async function uploadOne(item: QueuedPdf) {
    if (!policy || !gradeId || !subjectId) {
      setError("Select a curriculum, grade, and subject before uploading.");
      return;
    }
    if (!rightsConfirmed || !sourceName.trim() || !sourceUrl.trim() || rightsBasis.trim().length < 10) {
      setError("Enter source and rights details and confirm permission before uploading.");
      return;
    }
    if (!item.title.trim()) {
      setError(`Enter a title for ${item.file.name}.`);
      return;
    }
    const controller = new AbortController();
    controllers.current.set(item.id, controller);
    setQueue((previous) =>
      previous.map((entry) =>
        entry.id === item.id
          ? { ...entry, state: "uploading", loaded: 0, startedAt: Date.now(), error: undefined }
          : entry,
      ),
    );
    try {
      const result = await uploadAdminBook(item.file, metadataFor(item), {
        signal: controller.signal,
        existingSessionId: item.sessionId,
        onSession: (sessionId) =>
          setQueue((previous) =>
            previous.map((entry) => (entry.id === item.id ? { ...entry, sessionId } : entry)),
          ),
        onProgress: (loaded) =>
          setQueue((previous) =>
            previous.map((entry) => (entry.id === item.id ? { ...entry, loaded } : entry)),
          ),
      });
      setQueue((previous) =>
        previous.map((entry) =>
          entry.id === item.id
            ? {
                ...entry,
                state: "processing",
                loaded: item.file.size,
                sessionId: result.session.id,
                bookId: result.book.book_id,
              }
            : entry,
        ),
      );
      setNotice(`Uploaded ${item.title}. PDF validation and indexing are running in the background.`);
      await refreshBooks();
    } catch (uploadError: unknown) {
      const wasPaused =
        uploadError instanceof DOMException && uploadError.name === "AbortError";
      setQueue((previous) =>
        previous.map((entry) =>
          entry.id === item.id
            ? {
                ...entry,
                state: wasPaused ? "paused" : "failed",
                error: wasPaused
                  ? undefined
                  : uploadError instanceof Error
                    ? uploadError.message
                    : "The upload failed. Retry to resume from completed parts.",
              }
            : entry,
        ),
      );
    } finally {
      controllers.current.delete(item.id);
    }
  }

  async function startQueue() {
    const candidates = queue.filter((item) => item.state === "queued" || item.state === "paused");
    const concurrency = Math.max(1, Math.min(policy?.max_concurrent_uploads ?? 1, 3));
    let next = 0;
    const workers = Array.from({ length: Math.min(concurrency, candidates.length) }, async () => {
      while (next < candidates.length) {
        const current = candidates[next];
        next += 1;
        await uploadOne(current);
      }
    });
    await Promise.all(workers);
  }

  async function cancelItem(item: QueuedPdf) {
    controllers.current.get(item.id)?.abort();
    if (item.sessionId) {
      try {
        await cancelAdminBookUpload(item.sessionId);
      } catch (cancelError: unknown) {
        setError(cancelError instanceof Error ? cancelError.message : "Upload cancellation failed.");
        return;
      }
    }
    setQueue((previous) =>
      previous.map((entry) =>
        entry.id === item.id ? { ...entry, state: "cancelled" } : entry,
      ),
    );
  }

  async function retryBook(book: AdminBook) {
    setBusyBooks((previous) => [...previous, book.book_id]);
    try {
      await retryAdminBookProcessing(book.book_id, {
        use_ocr: useOcr,
        ocr_language: ocrLanguage,
      });
      setNotice(`Processing restarted for ${book.title}.`);
      await refreshBooks();
    } catch (retryError: unknown) {
      setError(retryError instanceof Error ? retryError.message : "Could not retry this book.");
    } finally {
      setBusyBooks((previous) => previous.filter((id) => id !== book.book_id));
    }
  }

  async function removeBook(book: AdminBook) {
    if (!window.confirm(`Delete the stored PDF and indexed text for “${book.title}”?`)) return;
    setBusyBooks((previous) => [...previous, book.book_id]);
    try {
      await deleteAdminBook(book.book_id);
      setNotice(`Deleted the uploaded PDF for ${book.title}.`);
      await refreshBooks();
    } catch (deleteError: unknown) {
      setError(deleteError instanceof Error ? deleteError.message : "Could not delete this book.");
    } finally {
      setBusyBooks((previous) => previous.filter((id) => id !== book.book_id));
    }
  }

  return (
    <section className="mx-auto max-w-7xl space-y-7 p-5 lg:p-9">
      <header className="rounded-[30px] bg-[var(--lav)] p-7 lg:p-9">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold">
              <BookOpen size={14} /> Administrator · shared curriculum library
            </p>
            <h1 className="mt-4 text-3xl font-bold">Curriculum books</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Resumable, checksum-verified PDF uploads. Files are transferred in bounded parts;
              processing continues in a background worker after upload.
            </p>
          </div>
          {policy ? (
            <div className="rounded-2xl bg-white/80 px-4 py-3 text-sm">
              <strong>{formatBytes(policy.max_size_bytes)}</strong> maximum per PDF
              <div className="mt-1 text-xs text-slate-500">
                {policy.provider === "s3" ? "Private multipart object storage" : "Configured local storage"}
              </div>
            </div>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-2xl bg-rose-50 p-4 text-sm text-rose-800" role="alert">
          <AlertCircle className="mt-0.5 shrink-0" size={17} /> {error}
        </div>
      ) : null}
      {notice ? (
        <div className="flex items-start gap-2 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800" role="status">
          <CheckCircle2 className="mt-0.5 shrink-0" size={17} /> {notice}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
        <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <h2 className="text-xl font-bold">Book details and upload</h2>
          <p className="mt-1 text-sm text-slate-500">
            Shared books require a real curriculum link and documented permission to store and process.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Curriculum
              <select className={inputClass} value={curriculumCode} onChange={(event) => setCurriculumCode(event.target.value)}>
                {curricula.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">
              Grade / class
              <select className={inputClass} value={gradeId} onChange={(event) => setGradeId(event.target.value)}>
                {grades.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">
              Subject
              <select className={inputClass} value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>
                {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">
              Author (optional)
              <input className={inputClass} maxLength={200} value={author} onChange={(event) => setAuthor(event.target.value)} />
            </label>
            <label className="text-sm font-medium">
              Language
              <input className={inputClass} maxLength={32} value={language} onChange={(event) => setLanguage(event.target.value)} />
            </label>
            <label className="text-sm font-medium">
              Academic year / edition (optional)
              <input className={inputClass} maxLength={120} value={edition} onChange={(event) => setEdition(event.target.value)} />
            </label>
            <label className="text-sm font-medium sm:col-span-2">
              Description (optional)
              <textarea className={inputClass} maxLength={2000} rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            <label className="text-sm font-medium">
              Source / publisher
              <input required className={inputClass} maxLength={160} value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
            </label>
            <label className="text-sm font-medium">
              Source URL (HTTPS)
              <input required type="url" className={inputClass} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
            </label>
            <label className="text-sm font-medium sm:col-span-2">
              Rights basis / permission details
              <textarea required className={inputClass} minLength={10} maxLength={2000} rows={2} value={rightsBasis} onChange={(event) => setRightsBasis(event.target.value)} />
            </label>
          </div>
          <label className="mt-3 flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} />
            I confirm this material may be stored and processed for the curriculum library.
          </label>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={useOcr} onChange={(event) => setUseOcr(event.target.checked)} />
              OCR text-only pages without embedded text
            </label>
            {useOcr ? (
              <select className="rounded-xl border border-slate-200 px-3 py-2 text-sm" value={ocrLanguage} onChange={(event) => setOcrLanguage(event.target.value as typeof ocrLanguage)}>
                <option value="eng">English</option>
                <option value="urd">Urdu</option>
                <option value="eng+urd">English and Urdu</option>
              </select>
            ) : null}
          </div>

          <button
            type="button"
            className={`mt-5 flex min-h-36 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed p-5 text-center transition ${dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}
            onClick={() => fileInput.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); void addFiles(event.dataTransfer.files); }}
          >
            <CloudUpload className="text-indigo-600" size={28} />
            <span className="mt-2 font-semibold">Drop PDFs here or choose files</span>
            <span className="mt-1 text-xs text-slate-500">
              PDF only · individual size limit {policy ? formatBytes(policy.max_size_bytes) : "loading…"} · resumable parts
            </span>
            <input ref={fileInput} className="hidden" type="file" accept=".pdf,application/pdf" multiple onChange={(event) => { if (event.target.files) void addFiles(event.target.files); event.currentTarget.value = ""; }} />
          </button>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className={buttonClass} type="button" disabled={!queue.some((item) => item.state === "queued" || item.state === "paused")} onClick={() => void startQueue()}>
              <CloudUpload size={16} /> Upload queued books
            </button>
            <p className="self-center text-xs text-slate-500">
              Max {policy?.max_concurrent_uploads ?? "—"} concurrent uploads per administrator
            </p>
          </div>
        </section>

        <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <h2 className="text-xl font-bold">Upload queue</h2>
          <p className="mt-1 text-sm text-slate-500">Transfer and PDF processing are shown as separate stages.</p>
          {queue.length === 0 ? (
            <div className="mt-7 rounded-2xl bg-slate-50 p-6 text-center text-sm text-slate-500">
              Selected PDFs will appear here with individual retry and pause controls.
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {queue.map((item) => {
                const percent = item.file.size ? Math.min(100, Math.round(item.loaded * 100 / item.file.size)) : 0;
                const elapsed = item.startedAt ? (Date.now() - item.startedAt) / 1000 : 0;
                const speed = elapsed > 0 ? item.loaded / elapsed : 0;
                const remaining = speed > 0 ? (item.file.size - item.loaded) / speed : 0;
                return (
                  <li key={item.id} className="rounded-2xl border border-slate-100 p-4">
                    <div className="flex items-start gap-3">
                      <FileText className="mt-1 shrink-0 text-indigo-600" size={18} />
                      <div className="min-w-0 flex-1">
                        <input aria-label={`Book title for ${item.file.name}`} className="w-full border-b border-transparent bg-transparent text-sm font-semibold outline-none focus:border-indigo-300" maxLength={200} value={item.title} onChange={(event) => setQueue((previous) => previous.map((entry) => entry.id === item.id ? { ...entry, title: event.target.value } : entry))} />
                        <div className="mt-1 truncate text-xs text-slate-500">{item.file.name} · {formatBytes(item.file.size)}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        {item.state === "uploading" ? (
                          <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`Pause ${item.file.name}`} onClick={() => controllers.current.get(item.id)?.abort()}><Pause size={16} /></button>
                        ) : null}
                        {item.state === "failed" || item.state === "paused" ? (
                          <button className="rounded-lg p-2 text-indigo-600 hover:bg-indigo-50" aria-label={`Retry ${item.file.name}`} onClick={() => void uploadOne(item)}><Play size={16} /></button>
                        ) : null}
                        {item.state !== "cancelled" &&
                        item.state !== "processing" &&
                        item.state !== "ready" &&
                        item.state !== "processingFailed" ? (
                          <button className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600" aria-label={`Cancel ${item.file.name}`} onClick={() => void cancelItem(item)}><X size={16} /></button>
                        ) : null}
                      </div>
                    </div>
                    {item.state === "uploading" || item.state === "paused" ? (
                      <div className="mt-3">
                        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-indigo-500 transition-[width]" style={{ width: `${percent}%` }} />
                        </div>
                        <div className="mt-1 flex justify-between gap-2 text-[11px] text-slate-500">
                          <span>{percent}% · {formatBytes(item.loaded)} / {formatBytes(item.file.size)}</span>
                          <span>{item.state === "paused" ? "Paused" : `${formatBytes(speed)}/s · ${formatDuration(remaining)} left`}</span>
                        </div>
                      </div>
                    ) : null}
                    <div className={`mt-2 text-xs ${item.state === "failed" ? "text-rose-700" : "text-slate-500"}`} role={item.state === "failed" ? "alert" : undefined}>
                      {item.error ?? queueStatus(item.state)}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>

      <section className="overflow-hidden rounded-[28px] bg-white shadow-[0_18px_45px_rgba(30,39,70,.09)]">
        <div className="flex flex-wrap items-center justify-between gap-3 p-6">
          <div>
            <h2 className="text-xl font-bold">Uploaded books</h2>
            <p className="mt-1 text-sm text-slate-500">Only books with completed processing are used for search and AI generation.</p>
          </div>
          <button className="rounded-xl border border-slate-200 p-2 text-slate-600" aria-label="Refresh books" onClick={() => void refreshBooks()}><RotateCcw size={16} /></button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-6 py-3">Book</th>
                <th className="px-4 py-3">Grade · subject</th>
                <th className="px-4 py-3">Size · pages</th>
                <th className="px-4 py-3">Processing</th>
                <th className="px-4 py-3">Uploaded</th>
                <th className="px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td className="px-6 py-8 text-slate-500" colSpan={6} role="status">Loading books…</td></tr>
              ) : books.length ? books.map((book) => (
                <tr key={book.book_id} className="align-top">
                  <td className="px-6 py-4">
                    <details>
                      <summary className="cursor-pointer font-semibold">{book.title}</summary>
                      <div className="mt-2 max-w-sm text-xs text-slate-500">
                        <p>{book.filename}</p>
                        {book.author ? <p>Author: {book.author}</p> : null}
                        <p>{book.curriculum} · {book.language}{book.edition ? ` · ${book.edition}` : ""}</p>
                        {book.description ? <p className="mt-1">{book.description}</p> : null}
                        {book.checksum_sha256 ? <p className="mt-1 break-all">SHA-256: {book.checksum_sha256}</p> : null}
                        {book.last_error ? <p className="mt-2 text-rose-700">Error: {book.last_error}</p> : null}
                      </div>
                    </details>
                  </td>
                  <td className="px-4 py-4">{book.grade} · {book.subject}</td>
                  <td className="px-4 py-4">{formatBytes(book.file_size)}<div className="text-xs text-slate-500">{book.page_count ? `${book.page_count} pages` : "Pages pending"}</div></td>
                  <td className="px-4 py-4">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${book.processing_status === "ready" ? "bg-emerald-50 text-emerald-700" : book.processing_status === "failed" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800"}`}>
                      {stageName(book.processing_stage)}
                    </span>
                    {book.processing_status === "processing" || book.processing_status === "queued" ? (
                      <div className="mt-2 h-1.5 w-28 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-indigo-500" style={{ width: `${book.processing_progress}%` }} /></div>
                    ) : null}
                    <div className="mt-1 text-[11px] text-slate-500">
                      {book.processing_status === "ready" ? "Ready for curriculum search" : `${book.processing_progress}%`}
                      {book.ocr_used ? " · OCR used" : ""}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-xs text-slate-500">{new Date(book.upload_date).toLocaleDateString()}</td>
                  <td className="px-6 py-4">
                    <div className="flex gap-1">
                      {book.processing_status === "failed" || book.processing_status === "ready" ? (
                        <button disabled={busyBooks.includes(book.book_id)} className="rounded-lg p-2 text-indigo-600 hover:bg-indigo-50 disabled:opacity-40" aria-label={`Retry processing ${book.title}`} onClick={() => void retryBook(book)}><RotateCcw size={16} /></button>
                      ) : null}
                      <button disabled={busyBooks.includes(book.book_id)} className="rounded-lg p-2 text-rose-600 hover:bg-rose-50 disabled:opacity-40" aria-label={`Delete ${book.title}`} onClick={() => void removeBook(book)}><Trash2 size={16} /></button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr><td className="px-6 py-8 text-slate-500" colSpan={6}>No admin-uploaded books yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 p-4">
          <button className="rounded-xl border border-slate-200 p-2 text-slate-600 disabled:opacity-40" aria-label="Previous books" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}><ChevronLeft size={17} /></button>
          <button className="rounded-xl border border-slate-200 p-2 text-slate-600 disabled:opacity-40" aria-label="Next books" disabled={books.length < 50} onClick={() => setOffset(offset + 50)}><ChevronRight size={17} /></button>
        </div>
      </section>
    </section>
  );
}

function formatBytes(value: number): string {
  if (value < 1) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function readSignature(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      if (!(reader.result instanceof ArrayBuffer)) {
        reject(new Error("Could not read the file signature."));
        return;
      }
      resolve(new TextDecoder().decode(reader.result));
    };
    reader.readAsArrayBuffer(file.slice(0, 5));
  });
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "estimating";
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const minutes = Math.ceil(seconds / 60);
  return `${Math.floor(minutes / 60) ? `${Math.floor(minutes / 60)}h ` : ""}${minutes % 60}m`;
}

function queueStatus(state: UploadState): string {
  switch (state) {
    case "queued": return "Queued";
    case "uploading": return "Uploading";
    case "paused": return "Paused; resume to continue from saved parts";
    case "processing": return "Upload complete; server-side PDF processing is underway";
    case "ready": return "Ready for search and AI study tools";
    case "processingFailed": return "PDF processing failed; use the book table's retry action";
    case "failed": return "Failed; retry resumes from successfully stored parts";
    case "cancelled": return "Cancelled";
  }
}

function stageName(stage: string): string {
  return stage.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
