'use client';

import { BookOpen, BrainCircuit, CheckCircle2, Clock3, RefreshCw, Sparkles, Wand2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  generateQuestions,
  getAIGenerationHistory,
  getAIInsights,
  type AIAnalyticsSummary,
  type AIHistoryEntry,
  type GeneratedQuestionItem,
  type GenerateRequest,
} from '../../../lib/api';

const defaultRequest: GenerateRequest = {
  curriculum: 'Punjab',
  subject: 'Mathematics',
  book: 'Mathematics 9',
  chapter: 'Algebra',
  topic: 'Linear equations',
  question_type: 'mcq',
  count: 5,
  difficulty: 'medium',
  language: 'en',
  grade: 'Grade 9',
  learning_objectives: 'Understand linear relationships and solve equations systematically.',
};

export default function AIGeneratorPage() {
  const [form, setForm] = useState<GenerateRequest>(defaultRequest);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [items, setItems] = useState<GeneratedQuestionItem[]>([]);
  const [history, setHistory] = useState<AIHistoryEntry[]>([]);
  const [insights, setInsights] = useState<AIAnalyticsSummary | null>(null);

  useEffect(() => {
    async function loadDashboard(): Promise<void> {
      try {
        const [entries, summary] = await Promise.all([
          getAIGenerationHistory(),
          getAIInsights(),
        ]);
        setHistory(entries);
        setInsights(summary);
      } catch (loadError) {
        console.error('Failed to load AI dashboard data', loadError);
      } finally {
        setIsLoadingHistory(false);
      }
    }

    void loadDashboard();
  }, []);

  function updateField<K extends keyof GenerateRequest>(field: K, value: GenerateRequest[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setMessage(null);

    try {
      const response = await generateQuestions(form);
      setItems(response.items);
      setMessage(response.message);
      const nextHistory = await getAIGenerationHistory();
      setHistory(nextHistory);
      const nextInsights = await getAIInsights();
      setInsights(nextInsights);
    } catch (submitError) {
      const messageText = submitError instanceof Error ? submitError.message : 'Unable to generate content.';
      setError(messageText);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-7xl p-5 lg:p-9">
      <div className="mb-6 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            AI generation workspace
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">AI generator</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            Generate curriculum-grounded MCQs, subjective prompts, quizzes, and assignments using the selected topic context and language.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-2xl bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
          <Sparkles size={16} />
          Active provider: local curriculum generator
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <form onSubmit={handleSubmit} className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--lav)] text-slate-800">
              <Wand2 size={18} />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Generation settings</h2>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Curriculum
              <input
                value={form.curriculum}
                onChange={(event) => updateField('curriculum', event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Grade / class
              <input
                value={form.grade ?? ''}
                onChange={(event) => updateField('grade', event.target.value || undefined)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Subject
              <input
                value={form.subject}
                onChange={(event) => updateField('subject', event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Book
              <input
                value={form.book}
                onChange={(event) => updateField('book', event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Chapter
              <input
                value={form.chapter}
                onChange={(event) => updateField('chapter', event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Topic
              <input
                value={form.topic}
                onChange={(event) => updateField('topic', event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Question type
              <select
                value={form.question_type}
                onChange={(event) => updateField('question_type', event.target.value as GenerateRequest['question_type'])}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              >
                <option value="mcq">MCQ</option>
                <option value="subjective">Subjective</option>
                <option value="quiz">Quiz</option>
                <option value="assignment">Assignment</option>
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700">
              Count
              <input
                type="number"
                min={1}
                max={10}
                value={form.count ?? 5}
                onChange={(event) => updateField('count', Number(event.target.value) || 1)}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Difficulty
              <select
                value={form.difficulty ?? 'medium'}
                onChange={(event) => updateField('difficulty', event.target.value as GenerateRequest['difficulty'])}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700">
              Language
              <select
                value={form.language ?? 'en'}
                onChange={(event) => updateField('language', event.target.value as GenerateRequest['language'])}
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
              >
                <option value="en">English</option>
                <option value="ur">Urdu</option>
              </select>
            </label>
          </div>

          <label className="mt-4 block text-sm font-medium text-slate-700">
            Learning objectives
            <textarea
              rows={3}
              value={form.learning_objectives ?? ''}
              onChange={(event) => updateField('learning_objectives', event.target.value || undefined)}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5"
            />
          </label>

          <div className="mt-6 flex items-center gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-2xl bg-[var(--lav)] px-4 py-2.5 font-semibold text-slate-900 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? <RefreshCw size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isSubmitting ? 'Generating…' : 'Generate content'}
            </button>
            <button
              type="button"
              onClick={() => setForm(defaultRequest)}
              className="rounded-2xl border border-slate-200 px-4 py-2.5 font-medium text-slate-700"
            >
              Reset
            </button>
          </div>

          {message ? (
            <div className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
              <CheckCircle2 size={16} /> {message}
            </div>
          ) : null}
          {error ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}
        </form>

        <aside className="space-y-5">
          <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--yellow)] text-slate-800">
                <BrainCircuit size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">AI insights</h2>
            </div>
            {isLoadingHistory ? (
              <div className="mt-4 text-sm text-slate-500">Loading insights…</div>
            ) : insights ? (
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
                  <div className="font-semibold text-slate-900">{insights.summary.total_generations} generations</div>
                  <div className="mt-1">Latest topic: {insights.summary.latest_topic}</div>
                </div>
                {insights.insights.map((insight) => (
                  <div key={insight.title} className="rounded-2xl border border-slate-200 p-3 text-sm text-slate-700">
                    <div className="font-semibold text-slate-900">{insight.title}</div>
                    <p className="mt-1">{insight.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 text-sm text-slate-500">No activity yet.</div>
            )}
          </div>

          <div className="rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--mint)] text-slate-800">
                <Clock3 size={18} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">Recent history</h2>
            </div>
            {history.length === 0 ? (
              <div className="mt-4 text-sm text-slate-500">No recent generations yet.</div>
            ) : (
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                {history.slice(0, 4).map((entry) => (
                  <li key={entry.id} className="rounded-2xl bg-slate-50 p-3">
                    <div className="font-semibold text-slate-900">{entry.topic}</div>
                    <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                      <span>{entry.question_type}</span>
                      <span>{entry.language}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>

      {items.length > 0 ? (
        <div className="mt-8 rounded-[28px] bg-white p-6 shadow-[0_18px_45px_rgba(30,39,70,.09)]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--pink)] text-slate-800">
              <BookOpen size={18} />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Preview</h2>
          </div>
          <div className="mt-6 space-y-5">
            {items.map((item, index) => (
              <article key={`${item.question ?? item.title ?? 'item'}-${index}`} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold uppercase tracking-[0.15em] text-slate-500">
                    {form.question_type}
                  </div>
                  <div className="text-xs text-slate-500">#{index + 1}</div>
                </div>
                {item.question ? (
                  <>
                    <p className="mt-2 text-base font-semibold text-slate-900">{item.question}</p>
                    {item.options ? (
                      <ul className="mt-3 space-y-2 text-sm text-slate-700">
                        {item.options.map((option) => (
                          <li key={option} className="rounded-xl bg-slate-50 px-3 py-2">{option}</li>
                        ))}
                      </ul>
                    ) : null}
                    <p className="mt-3 text-sm text-slate-700"><span className="font-semibold">Answer:</span> {item.correct_answer}</p>
                    <p className="mt-2 text-sm text-slate-600">{item.explanation}</p>
                  </>
                ) : (
                  <>
                    <p className="mt-2 text-base font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-2 text-sm text-slate-600">{item.instructions}</p>
                    {Array.isArray(item.tasks) ? (
                      <ul className="mt-3 space-y-2 text-sm text-slate-700">
                        {item.tasks.map((task, taskIndex) => (
                          <li key={`${task.task}-${taskIndex}`} className="rounded-xl bg-slate-50 px-3 py-2">
                            {task.task}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </>
                )}
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
