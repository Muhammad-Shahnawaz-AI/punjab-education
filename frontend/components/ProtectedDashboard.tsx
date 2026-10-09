"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { DashboardShell } from "./DashboardShell";
import { PublicReadOnlyShell } from "./PublicReadOnlyShell";

const teacherOnlyPaths = ["/ai-generator", "/students", "/analytics"];
const publicPreviewPaths = ["/", "/curriculum", "/admin"];

export function ProtectedDashboard({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (user === null && !publicPreviewPaths.includes(pathname)) {
      router.replace("/login");
      return;
    }
    if (user === null) return;
    if (
      user.role === "student" &&
      teacherOnlyPaths.some((path) => pathname.startsWith(path))
    ) {
      router.replace("/");
    }
    if (pathname.startsWith("/admin") && user.role !== "admin") {
      router.replace("/");
    }
  }, [isLoading, pathname, router, user]);

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center" role="status">
        <p className="rounded-2xl bg-white px-5 py-4 text-sm text-slate-600 shadow-sm">
          Loading your workspace...
        </p>
      </div>
    );
  }

  if (user === null) {
    if (!publicPreviewPaths.includes(pathname)) return null;
    return <PublicReadOnlyShell>{children}</PublicReadOnlyShell>;
  }

  if (
    (user.role === "student" &&
      teacherOnlyPaths.some((path) => pathname.startsWith(path))) ||
    (pathname.startsWith("/admin") && user.role !== "admin")
  ) {
    return null;
  }

  return (
    <DashboardShell user={user} onLogout={logout}>
      {children}
    </DashboardShell>
  );
}
