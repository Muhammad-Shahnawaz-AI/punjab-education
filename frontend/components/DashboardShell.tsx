'use client';

import {
  BarChart3,
  BookMarked,
  BookOpen,
  ChevronRight,
  ClipboardCheck,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldCheck,
  Settings,
  Sparkles,
  Users,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import type { AuthUser } from '../lib/api';

const navigation = [
  { label: 'Overview', href: '/', icon: LayoutDashboard },
  { label: 'Curriculum', href: '/curriculum', icon: BookOpen },
  { label: 'My Study Books', href: '/study-library', icon: BookMarked },
  { label: 'AI Generator', href: '/ai-generator', icon: Sparkles },
  { label: 'Assessments', href: '/assessments', icon: ClipboardCheck },
  { label: 'Students', href: '/students', icon: Users },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  { label: 'User Management', href: '/admin/users', icon: ShieldCheck },
];

export function DashboardShell({
  children,
  user,
  onLogout,
}: {
  children: ReactNode;
  user: AuthUser;
  onLogout: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="min-h-screen lg:flex">
      <aside
        className={`${menuOpen ? 'fixed inset-0 z-50 flex' : 'hidden'} w-full flex-col border-r border-slate-100 bg-white p-5 lg:static lg:flex lg:w-64`}
      >
        <div className="mb-10 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3" onClick={() => setMenuOpen(false)}>
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--lav)]">
              <GraduationCap size={22} />
            </span>
            <span>
              <span className="block font-bold">Punjab Edu</span>
              <span className="block text-xs text-slate-400">Intelligence Platform</span>
            </span>
          </Link>
          <button
            aria-label="Close navigation"
            className="lg:hidden"
            onClick={() => setMenuOpen(false)}
          >
            <X />
          </button>
        </div>
        <div className="mb-2 px-3 text-[11px] uppercase tracking-wider text-slate-400">
          Workspace
        </div>
        <nav aria-label="Main navigation" className="space-y-1">
          {navigation
            .filter(({ href }) => {
              if (href === '/admin/users') return user.role === 'admin';
              if (user.role === 'student') {
                return ['/', '/curriculum', '/assessments', '/study-library'].includes(href);
              }
              return href !== '/admin/users';
            })
            .map(({ label, href, icon: Icon }) => (
            <Link
              key={href}
              aria-current={pathname === href ? 'page' : undefined}
              href={href}
              onClick={() => setMenuOpen(false)}
              className={`flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-sm transition ${pathname === href ? 'bg-[var(--lav)] font-semibold' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              <Icon size={18} />
              {label}
              <ChevronRight className="ml-auto" size={15} />
            </Link>
            ))}
        </nav>
        {user.role !== 'student' && (
          <div className="mt-auto rounded-3xl bg-[var(--yellow)] p-4">
            <div className="text-sm font-semibold">AI content ready</div>
            <p className="mt-1 text-xs text-slate-600">
              Generate curriculum-aligned questions in seconds.
            </p>
            <Link
              href="/ai-generator"
              className="mt-3 inline-flex rounded-xl bg-white px-3 py-2 text-xs font-semibold"
            >
              Let&apos;s create
            </Link>
          </div>
        )}
        <Link
          href="/settings"
          className="mt-3 flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-500 hover:bg-slate-50"
        >
          <Settings size={18} /> Settings
        </Link>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-100 bg-white/90 px-5 backdrop-blur lg:px-9">
          <div className="flex items-center gap-3">
            <button
              aria-label="Open navigation"
              className="lg:hidden"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </button>
            <div>
              <div className="text-xs text-slate-400">{user.role}</div>
              <p className="text-xl font-semibold lg:text-2xl">{user.email}</p>
            </div>
          </div>
          <button
            aria-label="Sign out"
            className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={() => void onLogout()}
          >
            <LogOut size={18} /> <span className="hidden sm:inline">Sign out</span>
          </button>
        </header>
        {children}
      </main>
    </div>
  );
}