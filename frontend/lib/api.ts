export type Curriculum = {
  id: string;
  name: string;
  description: string;
  is_sample: boolean;
};

export type CurriculumResponse = {
  curricula: Curriculum[];
};

export type CatalogItem = {
  id: number;
  name: string;
};

export type CatalogResponse = {
  items: CatalogItem[];
};

export type HealthResponse = {
  status: string;
};

export type AuthRole = 'student' | 'teacher' | 'admin';

export type UserSettings = {
  full_name?: string;
  email?: string;
  department?: string;
  phone?: string;
  interface_language?: 'English' | 'Urdu' | 'Punjabi';
  time_zone?: string;
  date_format?: 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD';
  notifications?: {
    weekly_curriculum_summaries?: boolean;
    assessment_reminders?: boolean;
    ai_generated_content_alerts?: boolean;
  };
};

export type AuthUser = {
  id: number;
  email: string;
  role: AuthRole;
  settings?: Record<string, unknown>;
};

export type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  access_expires_in: number;
  user: AuthUser;
};

export type AdminUserInput = {
  email: string;
  password: string;
  role: AuthRole;
};

export type AdminUserListResponse = {
  users: AuthUser[];
};

export type GenerateRequest = {
  curriculum: string;
  subject: string;
  book: string;
  chapter: string;
  topic: string;
  question_type: 'mcq' | 'subjective' | 'quiz' | 'assignment';
  count?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  language?: 'en' | 'ur';
  grade?: string;
  learning_objectives?: string;
};

export type GeneratedQuestionItem = {
  question?: string;
  options?: string[];
  correct_answer?: string;
  explanation?: string;
  expected_answer?: string;
  title?: string;
  instructions?: string;
  tasks?: Array<{ task: string; marks?: number }>;
  marks?: number;
  topic?: string;
  difficulty?: string;
  language?: string;
  [key: string]: unknown;
};

export type GenerateResponse = {
  status: string;
  request: GenerateRequest & { count: number; difficulty: string; language: string };
  items: GeneratedQuestionItem[];
  message: string;
};

export type AIHistoryEntry = {
  id: number;
  question_type: string;
  subject: string;
  chapter: string;
  topic: string;
  difficulty: string;
  language: string;
  status: string;
  created_at: string;
};

export type AIInsight = {
  title: string;
  text: string;
};

export type AIAnalyticsSummary = {
  status: string;
  summary: {
    total_generations: number;
    latest_topic: string;
    preferred_language: string;
    latest_question_type: string;
  };
  insights: AIInsight[];
};

export type StudyBook = {
  id: number;
  title: string;
  filename: string;
  file_size: number;
  page_count: number;
  created_at: string;
};

export type StudyCitation = {
  book_id: number;
  book_title: string;
  page_number: number;
};

export type StudyChatResponse = {
  answer: string;
  citations: StudyCitation[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshPromise: Promise<AuthTokenResponse | null> | null = null;
let tokenUpdateListener: ((tokens: AuthTokenResponse) => void) | null = null;

export function setAuthTokens(access: string | null, refresh: string | null): void {
  accessToken = access;
  refreshToken = refresh;
}

export function setTokenUpdateListener(
  listener: ((tokens: AuthTokenResponse) => void) | null,
): void {
  tokenUpdateListener = listener;
}

async function performFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (accessToken !== null) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  return fetch(`${apiUrl}${path}`, { ...init, headers });
}

async function renewAuthSession(): Promise<AuthTokenResponse | null> {
  if (refreshToken === null) return null;
  if (refreshPromise !== null) return refreshPromise;

  const activeRefreshToken = refreshToken;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${apiUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: activeRefreshToken }),
      });
      if (!response.ok) {
        setAuthTokens(null, null);
        return null;
      }
      const tokens = (await response.json()) as AuthTokenResponse;
      setAuthTokens(tokens.access_token, tokens.refresh_token);
      tokenUpdateListener?.(tokens);
      return tokens;
    } catch {
      return null;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await performFetch(path, init);
    if (response.status === 401 && refreshToken !== null && path !== '/api/auth/refresh') {
      const tokens = await renewAuthSession();
      if (tokens !== null) response = await performFetch(path, init);
    }
  } catch {
    throw new ApiError('The education service is unavailable. Please try again.', 0);
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const message =
      typeof body === 'object' && body !== null && 'detail' in body &&
      typeof body.detail === 'string'
        ? body.detail
        : `The request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }

  if (response.headers.get('content-type')?.includes('application/pdf')) {
    return (await response.blob()) as T;
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export function getCurricula(): Promise<CurriculumResponse> {
  return request<CurriculumResponse>('/api/curriculum');
}

export function getGrades(curriculumCode: string): Promise<CatalogResponse> {
  return request<CatalogResponse>(`/api/curriculum/${encodeURIComponent(curriculumCode)}/grades`);
}

export function getSubjects(gradeId: number): Promise<CatalogResponse> {
  return request<CatalogResponse>(`/api/grades/${gradeId}/subjects`);
}

export function getBooks(subjectId: number): Promise<CatalogResponse> {
  return request<CatalogResponse>(`/api/subjects/${subjectId}/books`);
}

export function getChapters(bookId: number): Promise<CatalogResponse> {
  return request<CatalogResponse>(`/api/books/${bookId}/chapters`);
}

export function getTopics(chapterId: number): Promise<CatalogResponse> {
  return request<CatalogResponse>(`/api/chapters/${chapterId}/topics`);
}

export async function registerUser(email: string, password: string): Promise<AuthTokenResponse> {
  const tokens = await request<AuthTokenResponse>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  setAuthTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export async function loginUser(email: string, password: string): Promise<AuthTokenResponse> {
  const tokens = await request<AuthTokenResponse>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  setAuthTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>('/api/auth/me');
}

export function getUserSettings(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/auth/settings');
}

export function updateUserSettings(settings: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/auth/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  });
}

export async function refreshUserSession(): Promise<AuthTokenResponse> {
  const tokens = await renewAuthSession();
  if (tokens === null) {
    throw new ApiError('Your session expired. Please sign in again.', 401);
  }
  return tokens;
}

export async function logoutUser(refresh: string): Promise<void> {
  await request<{ status: string }>('/api/auth/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  setAuthTokens(null, null);
}

export function getAdminUsers(): Promise<AdminUserListResponse> {
  return request<AdminUserListResponse>('/api/auth/admin/users');
}

export function createAdminUser(input: AdminUserInput): Promise<AuthUser> {
  return request<AuthUser>('/api/auth/admin/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function generateQuestions(input: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>('/api/ai/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function getAIGenerationHistory(): Promise<AIHistoryEntry[]> {
  return request<AIHistoryEntry[]>('/api/ai/history');
}

export function getAIInsights(): Promise<AIAnalyticsSummary> {
  return request<AIAnalyticsSummary>('/api/ai/insights');
}

export function getAIRecommendations(): Promise<{ status: string; items: { topic: string; type: string; recommendation: string }[] }> {
  return request<{ status: string; items: { topic: string; type: string; recommendation: string }[] }>('/api/ai/recommendations');
}

export function getStudyBooks(): Promise<StudyBook[]> {
  return request<StudyBook[]>('/api/study/books');
}

export function uploadStudyBook(file: File, title: string): Promise<StudyBook> {
  const body = new FormData();
  body.append('file', file);
  body.append('title', title);
  return request<StudyBook>('/api/study/books', { method: 'POST', body });
}

export function getStudyBookPdf(bookId: number): Promise<Blob> {
  return request<Blob>(`/api/study/books/${bookId}/file`);
}

export function deleteStudyBook(bookId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/study/books/${bookId}`, { method: 'DELETE' });
}

export function askAboutBooks(
  bookIds: number[],
  prompt: string,
  language: 'en' | 'ur',
  imageData?: string | null,
  subject?: string,
  intent?: string,
  grade?: string,
): Promise<StudyChatResponse> {
  return request<StudyChatResponse>('/api/study/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      book_ids: bookIds,
      prompt,
      language,
      image_data: imageData ?? null,
      subject: subject ?? 'General Education',
      intent: intent ?? 'explain',
      grade: grade ?? 'General',
    }),
  });
}