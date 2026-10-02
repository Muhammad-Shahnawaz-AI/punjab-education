import type { ReactNode } from 'react';
import Link from 'next/link';

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-5">
      <div className="w-full max-w-md">
        <Link className="mb-6 inline-flex items-center gap-3" href="/">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--mint)] font-bold">PE</span>
          <span>
            <span className="block font-bold">Punjab Edu</span>
            <span className="block text-xs text-slate-500">Intelligence Platform</span>
          </span>
        </Link>
        {children}
      </div>
    </main>
  );
}