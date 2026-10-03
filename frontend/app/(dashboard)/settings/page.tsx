'use client';

import { Bell, Check, Globe, Lock, ShieldCheck, Sparkles, UserCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getCurrentUser, getUserSettings, updateUserSettings } from '../../../lib/api';

type NotificationSettings = {
  weekly_curriculum_summaries: boolean;
  assessment_reminders: boolean;
  ai_generated_content_alerts: boolean;
};

type SettingsFormState = {
  full_name: string;
  email: string;
  department: string;
  phone: string;
  interface_language: 'English' | 'Urdu' | 'Punjabi';
  time_zone: string;
  date_format: 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD';
  notifications: NotificationSettings;
};

const defaultNotifications: NotificationSettings = {
  weekly_curriculum_summaries: true,
  assessment_reminders: true,
  ai_generated_content_alerts: false,
};

const defaultSettings: SettingsFormState = {
  full_name: '',
  email: '',
  department: '',
  phone: '',
  interface_language: 'English',
  time_zone: 'Asia/Karachi',
  date_format: 'DD/MM/YYYY',
  notifications: defaultNotifications,
};

const languageOptions = ['English', 'Urdu', 'Punjabi'] as const;
const dateFormatOptions = ['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'] as const;

function readString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function isLanguage(value: unknown): value is SettingsFormState['interface_language'] {
  return value === 'English' || value === 'Urdu' || value === 'Punjabi';
}

function isDateFormat(value: unknown): value is SettingsFormState['date_format'] {
  return value === 'DD/MM/YYYY' || value === 'MM/DD/YYYY' || value === 'YYYY-MM-DD';
}

function normalizeSettings(
  data: Record<string, unknown> | null | undefined,
  fallbackEmail = '',
): SettingsFormState {
  const notificationInput =
    data && typeof data.notifications === 'object' && data.notifications !== null
      ? (data.notifications as Record<string, unknown>)
      : {};

  return {
    full_name: readString(data?.full_name),
    email: readString(data?.email) || fallbackEmail,
    department: readString(data?.department),
    phone: readString(data?.phone),
    interface_language: isLanguage(data?.interface_language) ? data.interface_language : 'English',
    time_zone: readString(data?.time_zone) || 'Asia/Karachi',
    date_format: isDateFormat(data?.date_format) ? data.date_format : 'DD/MM/YYYY',
    notifications: {
      weekly_curriculum_summaries: Boolean(
        notificationInput.weekly_curriculum_summaries ?? defaultNotifications.weekly_curriculum_summaries,
      ),
      assessment_reminders: Boolean(
        notificationInput.assessment_reminders ?? defaultNotifications.assessment_reminders,
      ),
      ai_generated_content_alerts: Boolean(
        notificationInput.ai_generated_content_alerts ?? defaultNotifications.ai_generated_content_alerts,
      ),
    },
  };
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsFormState>(defaultSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadSettings() {
      try {
        const [currentUser, savedSettings] = await Promise.all([
          getCurrentUser(),
          getUserSettings(),
        ]);

        if (!active) return;

        setSettings(
          normalizeSettings(savedSettings as Record<string, unknown>, currentUser.email),
        );
      } catch (error) {
        console.error('Failed to load settings', error);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    void loadSettings();
    return () => {
      active = false;
    };
  }, []);

  const initials = useMemo(() => {
    const source = settings.full_name || settings.email || 'User';
    const parts = source
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');

    return parts || 'U';
  }, [settings.email, settings.full_name]);

  const displayName = settings.full_name || settings.email || 'User';

  function updateField<K extends keyof SettingsFormState>(field: K, value: SettingsFormState[K]) {
    setSettings((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateNotification(key: keyof NotificationSettings) {
    setSettings((current) => ({
      ...current,
      notifications: {
        ...current.notifications,
        [key]: !current.notifications[key],
      },
    }));
  }

  async function handleSave() {
    setIsSaving(true);
    setStatusMessage(null);

    try {
      const saved = await updateUserSettings({
        full_name: settings.full_name,
        email: settings.email,
        department: settings.department,
        phone: settings.phone,
        interface_language: settings.interface_language,
        time_zone: settings.time_zone,
        date_format: settings.date_format,
        notifications: { ...settings.notifications },
      });

      setSettings(normalizeSettings(saved as Record<string, unknown>, settings.email));
      setStatusMessage('Saved');
    } catch (error) {
      console.error('Failed to save settings', error);
      setStatusMessage('Unable to save settings');
    } finally {
      setIsSaving(false);
    }
  }

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

        <div className="flex items-center gap-3">
          {statusMessage ? (
            <span className="text-sm font-medium text-emerald-700">{statusMessage}</span>
          ) : null}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isLoading || isSaving}
            className="inline-flex items-center justify-center rounded-2xl bg-[var(--lav)] px-5 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSaving ? 'Saving...' : 'Save changes'}
          </button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-5">
          <section className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-4 border-b border-slate-100 pb-5">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--lav)] text-lg font-bold text-slate-800">
                {initials}
              </div>
              <div>
                <p className="text-sm text-slate-400">Signed in as</p>
                <p className="text-xl font-semibold text-slate-900">{displayName}</p>
                <p className="text-sm text-slate-500">{settings.department || 'Teacher'} · Punjab Education</p>
              </div>
            </div>

            <div className="mt-6">
              <h2 className="text-xl font-bold text-slate-900">Profile details</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-slate-700">
                  Full name
                  <input
                    value={settings.full_name}
                    onChange={(event) => updateField('full_name', event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                    placeholder="Full name"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Email address
                  <input
                    value={settings.email}
                    onChange={(event) => updateField('email', event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                    placeholder="Email address"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Department
                  <input
                    value={settings.department}
                    onChange={(event) => updateField('department', event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                    placeholder="Department"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Phone
                  <input
                    value={settings.phone}
                    onChange={(event) => updateField('phone', event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-slate-300"
                    placeholder="Phone number"
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
                  {languageOptions.map((language) => (
                    <button
                      key={language}
                      type="button"
                      onClick={() => updateField('interface_language', language)}
                      className={`rounded-2xl border px-3 py-2 text-sm font-medium transition ${
                        settings.interface_language === language
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
                    value={settings.time_zone}
                    onChange={(event) => updateField('time_zone', event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none focus:border-slate-300"
                  >
                    <option value="Asia/Karachi">Asia/Karachi</option>
                    <option value="UTC">UTC</option>
                    <option value="Asia/Dubai">Asia/Dubai</option>
                  </select>
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Date format
                  <select
                    value={settings.date_format}
                    onChange={(event) => updateField('date_format', event.target.value as SettingsFormState['date_format'])}
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none focus:border-slate-300"
                  >
                    {dateFormatOptions.map((format) => (
                      <option key={format} value={format}>
                        {format}
                      </option>
                    ))}
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
                { key: 'weekly_curriculum_summaries', label: 'Weekly curriculum summaries' },
                { key: 'assessment_reminders', label: 'Assessment reminders' },
                { key: 'ai_generated_content_alerts', label: 'AI-generated content alerts' },
              ].map(({ key, label }) => {
                const active = settings.notifications[key as keyof NotificationSettings];
                return (
                  <label
                    key={label}
                    className="flex items-center justify-between gap-4 rounded-2xl bg-slate-50 p-3"
                  >
                    <span className="text-sm text-slate-700">{label}</span>
                    <button
                      type="button"
                      aria-label={`Toggle ${label}`}
                      aria-pressed={active}
                      onClick={() => updateNotification(key as keyof NotificationSettings)}
                      className={`relative h-7 w-12 rounded-full transition ${
                        active ? 'bg-slate-900' : 'bg-slate-300'
                      }`}
                    >
                      <span
                        className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow-sm transition ${
                          active ? 'left-6' : 'left-1'
                        }`}
                      />
                    </button>
                  </label>
                );
              })}
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
                <span className="inline-flex items-center gap-2">
                  <Lock size={16} /> Password
                </span>
                <span className="font-medium text-slate-900">••••••••</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
                <span className="inline-flex items-center gap-2">
                  <Sparkles size={16} /> Activity status
                </span>
                <span className="inline-flex items-center gap-2 font-medium text-emerald-600">
                  <Check size={14} /> Secure
                </span>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
                <span className="inline-flex items-center gap-2">
                  <UserCircle size={16} /> Access level
                </span>
                <span className="font-medium text-slate-900">Teacher</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
