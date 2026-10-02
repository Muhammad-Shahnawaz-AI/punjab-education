import type { ReactNode } from 'react';
import { ProtectedDashboard } from '../../components/ProtectedDashboard';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <ProtectedDashboard>{children}</ProtectedDashboard>;
}