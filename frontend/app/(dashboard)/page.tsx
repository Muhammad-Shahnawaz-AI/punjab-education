"use client";

import {
  BookOpen,
  ChevronRight,
  GraduationCap,
  LibraryBig,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getDashboardOverview, type DashboardOverview } from "../../lib/api";

export default function OverviewPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void getDashboardOverview()
      .then((data) => {
        if (active) setOverview(data);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load live curriculum data.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="rounded-[30px] bg-[var(--lav)] p-7 lg:p-9">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold">
            <GraduationCap size={14} /> Punjab curriculum workspace
          </div>
          <h1 className="mt-5 text-3xl font-bold leading-tight lg:text-4xl">
            Curriculum overview
          </h1>
          <p className="mt-3 text-slate-600">
            Live counts from the approved curriculum catalog. No sample mastery,
            student, or assessment metrics are shown.
          </p>
          <Link
            href="/curriculum"
            className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-[var(--pink)] px-5 py-3 font-semibold"
          >
            Browse curriculum <ChevronRight size={17} />
          </Link>
        </div>
      </div>

      {error ? (
        <p
          className="mt-5 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Curricula"
          value={overview?.curricula}
          isLoading={isLoading}
        />
        <Stat
          label="Approved books"
          value={overview?.approved_books}
          isLoading={isLoading}
        />
        <Stat
          label="Chapters"
          value={overview?.chapters}
          isLoading={isLoading}
        />
        <Stat label="Topics" value={overview?.topics} isLoading={isLoading} />
      </div>

      {overview && overview.curricula === 0 ? (
        <div className="mt-6 rounded-[28px] border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">
          No approved curriculum books are loaded yet. Add only material whose
          publisher permits storage and processing. Sample catalog records are
          excluded from these figures.
        </div>
      ) : null}

      <div className="mt-9 grid gap-5 xl:grid-cols-[1fr_.8fr]">
        <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--mint)]">
              <BookOpen size={18} />
            </div>
            <div>
              <h2 className="text-lg font-bold">Subjects in the catalog</h2>
              <p className="text-sm text-slate-400">
                Counts from real curriculum records
              </p>
            </div>
          </div>
          {isLoading ? (
            <p className="mt-5 text-sm text-slate-500" role="status">
              Loading catalog…
            </p>
          ) : overview?.subject_catalog.length ? (
            <ul className="mt-4 divide-y divide-slate-100">
              {overview.subject_catalog.map((subject) => (
                <li
                  key={subject.name}
                  className="flex flex-wrap items-center justify-between gap-2 py-3"
                >
                  <span className="font-semibold">{subject.name}</span>
                  <span className="text-xs text-slate-500">
                    {subject.books} books · {subject.chapters} chapters ·{" "}
                    {subject.topics} topics
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-sm text-slate-500">
              No approved subject records are available.
            </p>
          )}
        </div>

        <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--yellow)]">
              <LibraryBig size={18} />
            </div>
            <div>
              <h2 className="text-lg font-bold">Recent AI generations</h2>
              <p className="text-sm text-slate-400">Your own saved activity</p>
            </div>
          </div>
          {overview?.recent_generations.length ? (
            <ul className="mt-4 divide-y divide-slate-100">
              {overview.recent_generations.map((item, index) => (
                <li key={`${item.created_at}-${index}`} className="py-3">
                  <p className="text-sm font-semibold">{item.topic}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {item.subject} · {item.chapter} ·{" "}
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-sm text-slate-500">
              No saved generation activity is available for this session.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  isLoading,
}: {
  label: string;
  value: number | undefined;
  isLoading: boolean;
}) {
  return (
    <div className="rounded-[25px] bg-white p-5 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-bold">
        {isLoading ? "—" : (value ?? 0).toLocaleString()}
      </div>
    </div>
  );
}
