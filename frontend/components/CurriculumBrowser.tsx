"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import {
  getBooks,
  getChapters,
  getCurricula,
  getGrades,
  getSubjects,
  getTopics,
  type CatalogItem,
} from "../lib/api";

export function CurriculumBrowser() {
  const [curriculumCode, setCurriculumCode] = useState("");
  const [gradeId, setGradeId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [bookId, setBookId] = useState<number | "">("");
  const [chapterId, setChapterId] = useState<number | "">("");
  const [topicId, setTopicId] = useState<number | "">("");

  const curriculaQuery = useQuery({
    queryKey: ["curricula"],
    queryFn: getCurricula,
  });
  const gradesQuery = useQuery({
    queryKey: ["grades", curriculumCode],
    queryFn: () => getGrades(curriculumCode),
    enabled: curriculumCode !== "",
  });
  const subjectsQuery = useQuery({
    queryKey: ["subjects", gradeId],
    queryFn: () => getSubjects(gradeId as number),
    enabled: gradeId !== "",
  });
  const booksQuery = useQuery({
    queryKey: ["books", subjectId],
    queryFn: () => getBooks(subjectId as number),
    enabled: subjectId !== "",
  });
  const chaptersQuery = useQuery({
    queryKey: ["chapters", bookId],
    queryFn: () => getChapters(bookId as number),
    enabled: bookId !== "",
  });
  const topicsQuery = useQuery({
    queryKey: ["topics", chapterId],
    queryFn: () => getTopics(chapterId as number),
    enabled: chapterId !== "",
  });

  const curricula =
    curriculaQuery.data?.curricula.filter(
      (curriculum) => !curriculum.is_sample,
    ) ?? [];

  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)] lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-slate-500">
              Curriculum library
            </p>
            <h1 className="mt-2 text-2xl font-bold">
              Browse learning material
            </h1>
            <p className="mt-2 text-slate-600">
              Select each level to explore the available catalog.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div>
            <h2 className="font-semibold">More PCTB e-books</h2>
            <p className="mt-1 text-sm text-slate-600">
              Browse the full e-book directory maintained by Literaria Education
              Foundation. Books open at their linked source and are not hosted
              by this project.
            </p>
          </div>
          <a
            className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2"
            href="https://literaria.edu.pk/pctb-e-books/"
            target="_blank"
            rel="noreferrer"
          >
            Browse PCTB e-books <ExternalLink size={16} aria-hidden="true" />
          </a>
        </div>

        {curriculaQuery.isError && (
          <QueryError onRetry={() => void curriculaQuery.refetch()} />
        )}
        {!curriculaQuery.isLoading && !curriculaQuery.isError && curricula.length === 0 ? (
          <p className="mt-5 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900" role="status">
            No approved curriculum data is loaded yet. Import a textbook only after confirming its
            publisher permits storage and processing.
          </p>
        ) : null}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Selector
            label="Curriculum"
            value={curriculumCode}
            options={curricula.map(({ id, name }) => ({ id, name }))}
            loading={curriculaQuery.isLoading}
            enabled
            onChange={(value) => {
              setCurriculumCode(String(value));
              setGradeId("");
              setSubjectId("");
              setBookId("");
              setChapterId("");
              setTopicId("");
            }}
            onRetry={() => void curriculaQuery.refetch()}
            error={curriculaQuery.isError}
          />
          <Selector
            label="Grade"
            value={gradeId}
            options={gradesQuery.data?.items ?? []}
            loading={gradesQuery.isLoading}
            enabled={curriculumCode !== ""}
            onChange={(value) => {
              setGradeId(Number(value));
              setSubjectId("");
              setBookId("");
              setChapterId("");
              setTopicId("");
            }}
            onRetry={() => void gradesQuery.refetch()}
            error={gradesQuery.isError}
          />
          <Selector
            label="Subject"
            value={subjectId}
            options={subjectsQuery.data?.items ?? []}
            loading={subjectsQuery.isLoading}
            enabled={gradeId !== ""}
            onChange={(value) => {
              setSubjectId(Number(value));
              setBookId("");
              setChapterId("");
              setTopicId("");
            }}
            onRetry={() => void subjectsQuery.refetch()}
            error={subjectsQuery.isError}
          />
          <Selector
            label="Book"
            value={bookId}
            options={booksQuery.data?.items ?? []}
            loading={booksQuery.isLoading}
            enabled={subjectId !== ""}
            onChange={(value) => {
              setBookId(Number(value));
              setChapterId("");
              setTopicId("");
            }}
            onRetry={() => void booksQuery.refetch()}
            error={booksQuery.isError}
          />
          <Selector
            label="Chapter"
            value={chapterId}
            options={chaptersQuery.data?.items ?? []}
            loading={chaptersQuery.isLoading}
            enabled={bookId !== ""}
            onChange={(value) => {
              setChapterId(Number(value));
              setTopicId("");
            }}
            onRetry={() => void chaptersQuery.refetch()}
            error={chaptersQuery.isError}
          />
          <Selector
            label="Topic"
            value={topicId}
            options={topicsQuery.data?.items ?? []}
            loading={topicsQuery.isLoading}
            enabled={chapterId !== ""}
            onChange={(value) => setTopicId(Number(value))}
            onRetry={() => void topicsQuery.refetch()}
            error={topicsQuery.isError}
          />
        </div>
        {topicId !== "" && (
          <p
            className="mt-5 text-sm font-semibold text-slate-600"
            role="status"
          >
            Topic selected. Approved source material is required before
            generating questions.
          </p>
        )}
      </div>
    </section>
  );
}

function Selector({
  label,
  value,
  options,
  loading,
  enabled,
  error,
  onChange,
  onRetry,
}: {
  label: string;
  value: number | string;
  options: CatalogItem[] | { id: string; name: string }[];
  loading: boolean;
  enabled: boolean;
  error: boolean;
  onChange: (value: string) => void;
  onRetry: () => void;
}) {
  const optionsAvailable = options.length > 0;

  return (
    <div className="space-y-2">
      <label
        className="block text-sm font-semibold"
        htmlFor={`curriculum-${label.toLowerCase()}`}
      >
        {label}
      </label>
      <select
        id={`curriculum-${label.toLowerCase()}`}
        aria-label={label}
        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
        value={value}
        disabled={!enabled || loading || error}
        onChange={(event) => onChange(event.currentTarget.value)}
      >
        <option value="">Select {label.toLowerCase()}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
      {loading && (
        <p className="text-xs text-slate-500" role="status">
          Loading {label.toLowerCase()}...
        </p>
      )}
      {error && <QueryError onRetry={onRetry} />}
      {enabled && !loading && !error && !optionsAvailable && (
        <p className="text-xs text-slate-500">
          No {label.toLowerCase()} available.
        </p>
      )}
    </div>
  );
}

function QueryError({ onRetry }: { onRetry: () => void }) {
  return (
    <p className="text-sm text-red-700" role="alert">
      Could not load this catalog.{" "}
      <button className="font-semibold underline" onClick={onRetry}>
        Retry
      </button>
    </p>
  );
}
