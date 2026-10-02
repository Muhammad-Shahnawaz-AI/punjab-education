'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';
import { useAuth } from './AuthProvider';
import { DashboardShell } from './DashboardShell';

const teacherOnlyPaths = ['/ai-generator', '/students', '/analytics'];

export function ProtectedDashboard({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (user === null) {
      router.replace('/login');
      return;
    }
    if (
      user.role === 'student' &&
      teacherOnlyPaths.some((path) => pathname.startsWith(path))
    ) {
      router.replace('/');
    }
    if (pathname.startsWith('/admin') && user.role !== 'admin') {
      router.replace('/');
    }
  }, [isLoading, pathname, router, user]);

  if (isLoading || user === null) {
    return (
      <div className="grid min-h-screen place-items-center" role="status">
        <p className="rounded-2xl bg-white px-5 py-4 text-sm text-slate-600 shadow-sm">
          Loading your workspace...
        </p>
      </div>
    );
  }

  if (
    (user.role === 'student' && teacherOnlyPaths.some((path) => pathname.startsWith(path))) ||
    (pathname.startsWith('/admin') && user.role !== 'admin')
  ) {
    return null;
  }

  return (
    <DashboardShell user={user} onLogout={logout}>
      {children}
    </DashboardShell>
  );
}