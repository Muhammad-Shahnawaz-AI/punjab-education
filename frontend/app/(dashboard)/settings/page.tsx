import { Bell, Check, Globe, Lock, ShieldCheck, Sparkles, UserCircle } from 'lucide-react';

export default function SettingsPage() {
  return (
    <section className="mx-auto max-w-6xl p-5 lg:p-9">
      <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Workspace
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
            Workspace settings
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            Manage profile details and language preferences.
          </p>
        </div>

        <button
          type="button"
          className="inline-flex items-center justify-center rounded-2xl bg-[var(--lav)] px-5 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:-translate-y-0.5"
        >
          Save changes
        </button>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-5">
          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-4 border-b border-slate-100 pb-5">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--lav)] text-lg font-bold text-slate-800">
                SA
              </div>
              <div>
                <p className="text-sm text-slate-400">Signed in as</p>
                <p className="text-xl font-semibold">Sana Ali</p>
                <p className="text-sm text-slate-500">Teacher · Punjab Education</p>
              </div>
            </div>

            <div className="mt-6">
              <h2 className="text-xl font-bold text-slate-900">Profile details</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-slate-700">
                  Full name
                  <input
                    defaultValue="Sana Ali"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Email address
                  <input
                    defaultValue="sana.ali@punjabedu.example"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Department
                  <input
                    defaultValue="Science"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Phone
                  <input
                    defaultValue="+92 300 1234567"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                  />
                </label>
              </div>
            </div>
          </section>

          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--mint)] text-slate-800">
                <Globe size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">Language preferences</h2>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">Interface language</label>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  {['English', 'Urdu', 'Punjabi'].map((language, index) => (
                    <button
                      key={language}
                      type="button"
                      className={`rounded-2xl border px-3 py-2 text-sm font-medium transition ${
                        index === 0
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300'
                      }`}
                    >
                      {language}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-slate-700">
                  Time zone
                  <select
                    defaultValue="Asia/Karachi"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none focus:border-slate-300"
                  >
                    <option>Asia/Karachi</option>
                    <option>UTC</option>
                    <option>Asia/Dubai</option>
                  </select>
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Date format
                  <select
                    defaultValue="DD/MM/YYYY"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none focus:border-slate-300"
                  >
                    <option>DD/MM/YYYY</option>
                    <option>MM/DD/YYYY</option>
                    <option>YYYY-MM-DD</option>
                  </select>
                </label>
              </div>
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--yellow)] text-slate-800">
                <Bell size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">Notifications</h2>
            </div>

            <div className="mt-5 space-y-4">
              {[
                'Weekly curriculum summaries',
                'Assessment reminders',
                'AI-generated content alerts',
              ].map((label) => (
                <label key={label} className="flex items-center justify-between gap-4 rounded-2xl bg-slate-50 p-3">
                  <span className="text-sm text-slate-700">{label}</span>
                  <button
                    type="button"
                    aria-label={`Toggle ${label}`}
                    className="relative h-7 w-12 rounded-full bg-slate-300 transition"
                  >
                    <span className="absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow-sm" />
                  </button>
                </label>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--pink)] text-slate-800">
                <ShieldCheck size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">Security</h2>
            </div>

            <div className="mt-5 space-y-3">
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
                <span className="inline-flex items-center gap-2"><Lock size={16} /> Password</span>
                <span className="font-medium text-slate-500">Updated 2 months ago</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
                <span className="inline-flex items-center gap-2"><UserCircle size={16} /> Two-factor auth</span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">
                  <Check size={12} /> Enabled
                </span>
              </div>
            </div>
          </section>

          <section className="rounded-[28px] bg-[var(--lav)] p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/80 text-slate-800">
                <Sparkles size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">AI defaults</h2>
            </div>
            <p className="mt-3 text-sm text-slate-700">
              Preferred generation language is set to English with medium difficulty by default.
            </p>
          </section>
        </div>
      </div>
    </section>
  );
}