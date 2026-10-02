import { BookOpen, Brain, ChevronRight, Target } from 'lucide-react';
import Link from 'next/link';

const subjects = [
  { name: 'Mathematics', topics: 42, mastery: 84, color: 'var(--lav)' },
  { name: 'Physics', topics: 36, mastery: 76, color: 'var(--mint)' },
  { name: 'Computer Science', topics: 31, mastery: 88, color: 'var(--pink)' },
  { name: 'English', topics: 28, mastery: 72, color: 'var(--yellow)' },
];

const recentItems = [
  ['Algebra - Linear Equations', 'Mathematics', '12 MCQs', '2 min ago'],
  ["Newton's Laws", 'Physics', '8 MCQs', '18 min ago'],
  ['Data Structures', 'Computer Science', '10 MCQs', '1 hr ago'],
];

export default function OverviewPage() {
  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
        <div className="rounded-[30px] bg-[var(--lav)] p-7 lg:p-9">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold">
              <Brain size={14} /> AI learning assistant
            </div>
            <h1 className="mt-5 text-3xl font-bold leading-tight lg:text-4xl">
              Build better learning journeys from the Punjab curriculum.
            </h1>
            <p className="mt-3 max-w-lg text-slate-600">
              Explore curriculum, prepare assessments, and turn student attempts into actionable
              insights.
            </p>
            <Link
              href="/ai-generator"
              className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-[var(--pink)] px-5 py-3 font-semibold"
            >
              Start generating <ChevronRight size={17} />
            </Link>
          </div>
        </div>
        <div className="rounded-[30px] bg-white p-7 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex justify-between">
            <div>
              <div className="text-sm text-slate-400">Sample overview</div>
              <div className="mt-1 text-3xl font-bold">82%</div>
              <div className="mt-1 text-sm text-slate-500">Average student mastery</div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--mint)]">
              <Target />
            </div>
          </div>
          <div className="mt-7 h-3 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full w-[82%] rounded-full bg-[var(--mint)]" />
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <Stat label="Active students" value="1,248" />
            <Stat label="Assessments" value="326" />
          </div>
          <p className="mt-3 text-xs text-slate-400">Illustrative data until analytics are connected.</p>
        </div>
      </div>

      <div className="mb-4 mt-9 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Curriculum overview</h2>
          <p className="mt-1 text-sm text-slate-400">Explore your active subjects and topics.</p>
        </div>
        <Link href="/curriculum" className="flex items-center gap-1 text-sm font-semibold">
          View all <ChevronRight size={16} />
        </Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {subjects.map((subject) => (
          <article key={subject.name} className="rounded-[25px] bg-white p-5 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div
              className="flex h-11 w-11 items-center justify-center rounded-2xl"
              style={{ background: subject.color }}
            >
              <BookOpen size={20} />
            </div>
            <h3 className="mt-4 font-semibold">{subject.name}</h3>
            <p className="mt-1 text-sm text-slate-400">{subject.topics} topics</p>
            <div className="mt-4 flex items-center justify-between text-xs">
              <span className="text-slate-400">Sample mastery</span>
              <b>{subject.mastery}%</b>
            </div>
            <div className="mt-2 h-2 rounded-full bg-slate-100">
              <div
                className="h-full rounded-full"
                style={{ width: `${subject.mastery}%`, background: subject.color }}
              />
            </div>
          </article>
        ))}
      </div>

      <div className="mt-9 grid gap-5 xl:grid-cols-[1fr_.8fr]">
        <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold">Recent AI-generated content</h2>
              <p className="text-sm text-slate-400">Sample items</p>
            </div>
            <Link
              aria-label="Open AI Generator"
              href="/ai-generator"
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--yellow)]"
            >
              <ChevronRight size={18} />
            </Link>
          </div>
          <div className="mt-5 divide-y divide-slate-100">
            {recentItems.map(([title, subject, count, time]) => (
              <div key={title} className="flex items-center gap-4 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50">
                  <Brain size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{title}</div>
                  <div className="mt-1 text-xs text-slate-400">{subject} · {count}</div>
                </div>
                <span className="text-xs text-slate-400">{time}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <h2 className="text-lg font-bold">Quick actions</h2>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <QuickAction href="/ai-generator" title="Generate MCQs" color="var(--lav)" />
            <QuickAction href="/assessments" title="Create quiz" color="var(--pink)" />
            <QuickAction href="/students" title="View students" color="var(--mint)" />
            <QuickAction href="/analytics" title="Open analytics" color="var(--yellow)" />
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 font-bold">{value}</div>
    </div>
  );
}

function QuickAction({ href, title, color }: { href: string; title: string; color: string }) {
  return (
    <Link
      href={href}
      className="rounded-2xl p-4 transition hover:-translate-y-0.5"
      style={{ background: color }}
    >
      <span className="block text-sm font-semibold">{title}</span>
      <ChevronRight size={16} className="mt-3" />
    </Link>
  );
}