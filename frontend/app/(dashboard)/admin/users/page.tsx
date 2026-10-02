'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { ApiError, createAdminUser, getAdminUsers, type AuthRole } from '../../../../lib/api';

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ['admin-users'], queryFn: getAdminUsers });
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<AuthRole>('teacher');
  const createUser = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      setEmail('');
      setPassword('');
      void queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createUser.mutate({ email, password, role });
  }

  return (
    <section className="mx-auto max-w-7xl space-y-5 p-5 lg:p-9">
      <header>
        <p className="text-sm font-semibold text-slate-500">Administration</p>
        <h1 className="mt-2 text-2xl font-bold">User management</h1>
      </header>
      <div className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
        <form className="space-y-4 rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]" onSubmit={submit}>
          <h2 className="font-bold">Create account</h2>
          <label className="block text-sm font-semibold" htmlFor="new-user-email">Email</label>
          <input id="new-user-email" className="w-full rounded-xl border border-slate-200 px-3 py-2" type="email" required value={email} onChange={(event) => setEmail(event.currentTarget.value)} />
          <label className="block text-sm font-semibold" htmlFor="new-user-password">Temporary password</label>
          <input id="new-user-password" className="w-full rounded-xl border border-slate-200 px-3 py-2" type="password" minLength={12} maxLength={128} required value={password} onChange={(event) => setPassword(event.currentTarget.value)} />
          <label className="block text-sm font-semibold" htmlFor="new-user-role">Role</label>
          <select id="new-user-role" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2" value={role} onChange={(event) => setRole(event.currentTarget.value as AuthRole)}>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
            <option value="admin">Admin</option>
          </select>
          {createUser.isError && <p className="text-sm text-red-700" role="alert">{createUser.error instanceof ApiError ? createUser.error.message : 'Unable to create account.'}</p>}
          <button className="rounded-xl bg-[var(--lav)] px-4 py-2 font-semibold disabled:opacity-60" disabled={createUser.isPending} type="submit">Create account</button>
        </form>
        <div className="overflow-hidden rounded-[28px] bg-white shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="border-b border-slate-100 p-6"><h2 className="font-bold">Accounts</h2></div>
          {usersQuery.isLoading && <p className="p-6 text-sm text-slate-500" role="status">Loading users...</p>}
          {usersQuery.isError && <p className="p-6 text-sm text-red-700" role="alert">Unable to load users.</p>}
          {usersQuery.data && usersQuery.data.users.length === 0 && <p className="p-6 text-sm text-slate-500">No accounts yet.</p>}
          {usersQuery.data && usersQuery.data.users.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-5 py-3">Email</th><th className="px-5 py-3">Role</th></tr></thead>
                <tbody className="divide-y divide-slate-100">{usersQuery.data.users.map((user) => <tr key={user.id}><td className="px-5 py-4">{user.email}</td><td className="px-5 py-4 capitalize">{user.role}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}