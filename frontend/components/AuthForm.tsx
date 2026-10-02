'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ApiError } from '../lib/api';
import { useAuth } from './AuthProvider';

export function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const { login, register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === 'register';

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (isRegister) await register(email, password);
      else await login(email, password);
      router.replace('/');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to sign in. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="w-full max-w-md rounded-[28px] bg-white p-7 shadow-[0_18px_45px_rgba(30,39,70,.09)] sm:p-9">
      <p className="text-sm font-semibold text-slate-500">{isRegister ? 'Student account' : 'Welcome back'}</p>
      <h1 className="mt-2 text-2xl font-bold">{isRegister ? 'Create your account' : 'Sign in'}</h1>
      <p className="mt-2 text-sm text-slate-600">
        {isRegister ? 'New accounts are created with student access.' : 'Use your education platform account.'}
      </p>
      <form className="mt-7 space-y-5" onSubmit={submit}>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="auth-email">Email</label>
          <input
            autoComplete="email"
            className="w-full rounded-2xl border border-slate-200 px-4 py-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            id="auth-email"
            name="email"
            onChange={(event) => setEmail(event.currentTarget.value)}
            required
            type="email"
            value={email}
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="auth-password">Password</label>
          <input
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            className="w-full rounded-2xl border border-slate-200 px-4 py-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            id="auth-password"
            maxLength={128}
            minLength={isRegister ? 12 : 1}
            name="password"
            onChange={(event) => setPassword(event.currentTarget.value)}
            required
            type="password"
            value={password}
          />
          {isRegister && <p className="mt-2 text-xs text-slate-500">Use at least 12 characters.</p>}
        </div>
        {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
        <button
          className="w-full rounded-2xl bg-[var(--lav)] px-5 py-3 font-semibold disabled:opacity-60"
          disabled={submitting}
          type="submit"
        >
          {submitting ? 'Please wait...' : isRegister ? 'Create account' : 'Sign in'}
        </button>
      </form>
      <p className="mt-6 text-sm text-slate-600">
        {isRegister ? 'Already registered?' : 'Need a student account?'}{' '}
        <Link className="font-semibold underline" href={isRegister ? '/login' : '/register'}>
          {isRegister ? 'Sign in' : 'Register'}
        </Link>
      </p>
    </section>
  );
}