import { BookOpen, GraduationCap } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function PublicReadOnlyShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--page)]">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 bg-white px-5 py-4 lg:px-9">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--lav)]">
            <GraduationCap size={22} />
          </span>
          <span>
            <span className="block font-bold">Punjab Edu</span>
            <span className="block text-xs text-slate-400">
              Read-only admin preview
            </span>
          </span>
        </Link>
        <nav
          aria-label="Public preview navigation"
          className="flex items-center gap-4 text-sm"
        >
          <Link className="inline-flex items-center gap-2" href="/curriculum">
            <BookOpen size={16} /> Curriculum
          </Link>
          <Link
            className="rounded-xl bg-[var(--lav)] px-4 py-2 font-semibold"
            href="/login"
          >
            Sign in for admin actions
          </Link>
        </nav>
      </header>
      <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-center text-sm text-amber-950">
        Public testing preview: data is read-only. User management, imports,
        study libraries, and other privileged operations still require
        authentication.
      </div>
      {children}
    </div>
  );
}
