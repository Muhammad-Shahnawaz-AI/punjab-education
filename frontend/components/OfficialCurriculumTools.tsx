"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  getCurrentUser,
  importOfficialBook,
  searchOfficialContent,
  type OfficialBookImportResponse,
  type OfficialBookSearchResult,
} from "../lib/api";

const outlineExample =
  '[{"name":"Algebra","start_page":1,"topics":["Linear equations"]}]';

export function OfficialCurriculumTools() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<OfficialBookSearchResult[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] =
    useState<OfficialBookImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then((user) => {
        if (active) {
          setIsAuthenticated(true);
          setIsAdmin(user.role === "admin");
        }
      })
      .catch(() => {
        if (active) setIsAdmin(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (query.trim().length < 2) {
      setError(
        "Enter at least two characters to search the indexed textbook content.",
      );
      return;
    }
    setError(null);
    setIsSearching(true);
    try {
      setResults(await searchOfficialContent(query.trim()));
    } catch (searchError) {
      setError(
        searchError instanceof Error
          ? searchError.message
          : "Unable to search curriculum.",
      );
    } finally {
      setIsSearching(false);
    }
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) {
      setError("Choose a PDF textbook to import.");
      return;
    }
    setError(null);
    setImportResult(null);
    setIsImporting(true);
    const body = new FormData(form);
    body.set("file", file);
    try {
      setImportResult(await importOfficialBook(body));
      form.reset();
      setFile(null);
    } catch (importError) {
      setError(
        importError instanceof Error
          ? importError.message
          : "Unable to import this PDF.",
      );
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <section className="mx-auto max-w-7xl space-y-5 px-5 pb-9">
      {isAuthenticated ? (
        <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <h2 className="text-xl font-bold">Search textbook content</h2>
          <p className="mt-1 text-sm text-slate-500">
            Search page-indexed excerpts from approved curriculum books.
          </p>
          <form
            className="mt-4 flex flex-col gap-3 sm:flex-row"
            onSubmit={(event) => void handleSearch(event)}
          >
            <label className="sr-only" htmlFor="official-content-query">
              Textbook search
            </label>
            <input
              id="official-content-query"
              className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-3"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search a concept or phrase"
            />
            <button
              className="rounded-2xl bg-[var(--lav)] px-5 py-3 font-semibold disabled:opacity-60"
              disabled={isSearching}
              type="submit"
            >
              {isSearching ? "Searching…" : "Search"}
            </button>
          </form>
          {results.length > 0 ? (
            <div className="mt-4 divide-y divide-slate-100">
              {results.map((result, index) => (
                <article
                  className="py-4"
                  key={`${result.book_id}-${result.page_number}-${index}`}
                >
                  <div className="text-sm font-semibold">
                    Grade {result.grade} · {result.subject} · {result.book}
                    {result.chapter ? ` · ${result.chapter}` : ""} · p.{" "}
                    {result.page_number}
                  </div>
                  <p className="mt-2 text-sm text-slate-700">
                    {result.excerpt}
                  </p>
                  <a
                    className="mt-2 inline-block text-xs text-slate-500 underline"
                    href={result.source_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Source: {result.source_name}
                  </a>
                  <p className="mt-1 text-xs text-slate-500">
                    Rights basis recorded: {result.rights_basis}
                  </p>
                </article>
              ))}
            </div>
          ) : query && !isSearching ? (
            <p className="mt-4 text-sm text-slate-500">
              No matching approved textbook excerpts.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="rounded-[28px] bg-white p-6 text-sm text-slate-600 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          Sign in to search indexed textbook excerpts. Public visitors can
          browse the curriculum catalog, but textbook contents are not publicly
          exposed.
        </div>
      )}

      {isAdmin ? (
        <form
          className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]"
          onSubmit={(event) => void handleImport(event)}
        >
          <h2 className="text-xl font-bold">Import an approved textbook</h2>
          <p className="mt-1 text-sm text-slate-500">
            Upload only after confirming the publisher permits storing and
            processing this book. The source URL is recorded for attribution; it
            is not automatically downloaded.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field
              label="Curriculum name"
              name="curriculum_name"
              value="Punjab Board"
            />
            <Field
              label="Curriculum code"
              name="curriculum_code"
              value="punjab-board"
            />
            <Field label="Grade" name="grade_level" type="number" value="9" />
            <Field
              label="Subject"
              name="subject_name"
              value=""
              placeholder="Mathematics"
            />
            <Field
              label="Book title / edition"
              name="book_name"
              value=""
              placeholder="Mathematics 9 (2026)"
            />
            <Field
              label="Source name"
              name="source_name"
              value=""
              placeholder="Publisher or site"
            />
            <Field
              label="HTTPS source URL"
              name="source_url"
              type="url"
              value=""
              placeholder="https://..."
            />
          </div>
          <label className="mt-4 block text-sm font-medium">
            Rights basis / permission record
            <textarea
              className="mt-2 min-h-20 w-full rounded-2xl border border-slate-200 px-3 py-2"
              name="rights_basis"
              minLength={10}
              maxLength={2000}
              required
            />
          </label>
          <label className="mt-4 block text-sm font-medium">
            Reviewed chapter outline (JSON, optional if headings are detectable)
            <textarea
              className="mt-2 min-h-24 w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-xs"
              name="outline"
              placeholder={outlineExample}
            />
          </label>
          <label className="mt-4 flex items-start gap-2 text-sm">
            <input
              className="mt-1"
              name="rights_confirmed"
              type="checkbox"
              value="true"
              required
            />
            I confirm that permission or an applicable license allows this
            platform to store and process the uploaded textbook.
          </label>
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input name="use_ocr" type="checkbox" value="true" />
            Run OCR on image-only pages (requires Tesseract to be installed on
            the API service).
          </label>
          <label className="mt-3 block text-sm font-medium">
            OCR language
            <select
              className="mt-2 rounded-2xl border border-slate-200 px-3 py-2"
              defaultValue="eng"
              name="ocr_language"
            >
              <option value="eng">English</option>
              <option value="urd">Urdu</option>
              <option value="eng+urd">English and Urdu</option>
            </select>
          </label>
          <label className="mt-4 block text-sm font-medium">
            PDF textbook (maximum 50 MB)
            <input
              className="mt-2 block w-full text-sm"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>
          <button
            className="mt-5 rounded-2xl bg-[var(--pink)] px-5 py-3 font-semibold disabled:opacity-60"
            disabled={isImporting}
            type="submit"
          >
            {isImporting ? "Importing and indexing…" : "Import and index PDF"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p
          className="rounded-2xl bg-rose-50 p-3 text-sm text-rose-700"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {importResult ? (
        <p
          className="rounded-2xl bg-emerald-50 p-3 text-sm text-emerald-700"
          role="status"
        >
          Imported {importResult.book}: {importResult.chapters} chapters and{" "}
          {importResult.indexed_chunks} searchable excerpts from{" "}
          {importResult.page_count} pages.
        </p>
      ) : null}
    </section>
  );
}

function Field({
  label,
  name,
  value,
  type = "text",
  placeholder,
}: {
  label: string;
  name: string;
  value: string;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2"
        defaultValue={value}
        name={name}
        placeholder={placeholder}
        required
        type={type}
      />
    </label>
  );
}
