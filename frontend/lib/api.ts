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

export type DashboardOverview = {
  curricula: number;
  grades: number;
  subjects: number;
  books: number;
  approved_books: number;
  chapters: number;
  topics: number;
  subject_catalog: {
    name: string;
    books: number;
    chapters: number;
    topics: number;
  }[];
  recent_generations: {
    subject: string;
    chapter: string;
    topic: string;
    created_at: string;
  }[];
};

export type OfficialBookSearchResult = {
  book_id: number;
  book: string;
  curriculum: string;
  grade: number;
  subject: string;
  chapter: string | null;
  topic: string | null;
  page_number: number;
  excerpt: string;
  source_name: string;
  source_url: string;
  rights_basis: string;
};

export type OfficialBookImportResponse = {
  status: string;
  book_id: number;
  book: string;
  grade: number;
  subject: string;
  chapters: number;
  indexed_chunks: number;
  page_count: number;
  ocr_used: boolean;
  rights_basis: string;
  source_url: string;
};

export type AdminBookUploadMetadata = {
  title: string;
  author?: string;
  grade_id: number;
  subject_id: number;
  source_name: string;
  source_url: string;
  rights_basis: string;
  rights_confirmed: boolean;
  language: string;
  edition?: string;
  description?: string;
  use_ocr: boolean;
  ocr_language: "eng" | "urd" | "eng+urd";
};

export type AdminBookUploadSession = {
  id: string;
  status: string;
  filename: string;
  file_size: number;
  part_size: number;
  part_count: number;
  uploaded_bytes: number;
  uploaded_parts: Record<string, number>;
  provider: "local" | "s3";
  expires_at: string;
  book_id: number | null;
};

export type AdminBook = {
  book_id: number;
  title: string;
  filename: string;
  file_size: number;
  grade: number;
  subject: string;
  curriculum: string;
  author: string | null;
  language: string;
  edition: string | null;
  description: string | null;
  upload_date: string;
  upload_status: string;
  processing_status: "queued" | "processing" | "ready" | "failed";
  processing_stage: string;
  processing_progress: number;
  page_count: number;
  ocr_used: boolean;
  last_error: string | null;
  retry_count: number;
  checksum_sha256: string | null;
};

export type AdminBookUploadPolicy = {
  max_size_bytes: number;
  part_size_bytes: number;
  max_concurrent_uploads: number;
  provider: "local" | "s3";
};

export type HealthResponse = {
  status: string;
};

export type AuthRole = "student" | "teacher" | "admin";

export type UserSettings = {
  full_name?: string;
  email?: string;
  department?: string;
  phone?: string;
  interface_language?: "English" | "Urdu" | "Punjabi";
  time_zone?: string;
  date_format?: "DD/MM/YYYY" | "MM/DD/YYYY" | "YYYY-MM-DD";
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
  token_type: "bearer";
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
  question_type: "mcq" | "subjective" | "quiz" | "assignment";
  count?: number;
  difficulty?: "easy" | "medium" | "hard";
  language?: "en" | "ur";
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
  request: GenerateRequest & {
    count: number;
    difficulty: string;
    language: string;
  };
  items: GeneratedQuestionItem[];
  sources?: {
    book: string;
    chapter: string;
    page: number;
    source_name: string;
    source_url: string;
  }[];
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

export type CurriculumStudyBook = {
  id: number;
  title: string;
  grade: number;
  subject: string;
  curriculum: string;
  page_count: number;
};

export type StudyCitation = {
  book_id: number;
  book_title: string;
  page_number: number;
  source_type?: "curriculum";
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
    this.name = "ApiError";
  }
}

const apiUrl = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshPromise: Promise<AuthTokenResponse | null> | null = null;
let tokenUpdateListener: ((tokens: AuthTokenResponse) => void) | null = null;

export function setAuthTokens(
  access: string | null,
  refresh: string | null,
): void {
  accessToken = access;
  refreshToken = refresh;
}

export function setTokenUpdateListener(
  listener: ((tokens: AuthTokenResponse) => void) | null,
): void {
  tokenUpdateListener = listener;
}

async function performFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (accessToken !== null) {
    headers.set("Authorization", `Bearer ${accessToken}`);
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
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    if (
      response.status === 401 &&
      refreshToken !== null &&
      path !== "/api/auth/refresh"
    ) {
      const tokens = await renewAuthSession();
      if (tokens !== null) response = await performFetch(path, init);
    }
  } catch {
    throw new ApiError(
      "The education service is unavailable. Please try again.",
      0,
    );
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const message =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : `The request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  if (response.headers.get("content-type")?.includes("application/pdf")) {
    return (await response.blob()) as T;
  }
  return (await response.json()) as T;
}

export function getAdminBooks(offset = 0, limit = 50): Promise<AdminBook[]> {
  return request<AdminBook[]>(`/api/admin/books?offset=${offset}&limit=${limit}`);
}

export function getAdminBookUploadPolicy(): Promise<AdminBookUploadPolicy> {
  return request<AdminBookUploadPolicy>("/api/admin/books/upload-policy");
}

export function getAdminBook(bookId: number): Promise<AdminBook> {
  return request<AdminBook>(`/api/admin/books/${bookId}`);
}

export function retryAdminBookProcessing(
  bookId: number,
  options: { use_ocr?: boolean; ocr_language?: "eng" | "urd" | "eng+urd" } = {},
): Promise<AdminBook> {
  return request<AdminBook>(`/api/admin/books/${bookId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
}

export function deleteAdminBook(bookId: number): Promise<void> {
  return request<void>(`/api/admin/books/${bookId}`, { method: "DELETE" });
}

export function cancelAdminBookUpload(uploadId: string): Promise<void> {
  return request<void>(`/api/admin/books/uploads/${uploadId}`, { method: "DELETE" });
}

async function putPart(
  url: string,
  body: Blob,
  headers: Record<string, string>,
  signal: AbortSignal,
  onProgress: (loaded: number) => void,
): Promise<void> {
  const attempt = (retry: boolean): Promise<void> =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", url);
      for (const [name, value] of Object.entries(headers)) {
        xhr.setRequestHeader(name, value);
      }
      if (url.startsWith(apiUrl)) {
        if (accessToken !== null) {
          xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
        }
      }
      const abort = () => xhr.abort();
      signal.addEventListener("abort", abort, { once: true });
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded);
      };
      xhr.onerror = () => {
        signal.removeEventListener("abort", abort);
        reject(new ApiError("The upload connection failed. Retry this part.", 0));
      };
      xhr.onabort = () => {
        signal.removeEventListener("abort", abort);
        reject(new DOMException("Upload paused.", "AbortError"));
      };
      xhr.onload = () => {
        signal.removeEventListener("abort", abort);
        if (xhr.status === 401 && retry && refreshToken !== null) {
          void renewAuthSession().then((tokens) => {
            if (tokens) {
              void attempt(false).then(resolve, reject);
            } else {
              reject(new ApiError("Your session expired. Please sign in again.", 401));
            }
          });
        } else if (xhr.status < 200 || xhr.status >= 300) {
          let message = `The upload part failed (${xhr.status}).`;
          try {
            const response = JSON.parse(xhr.responseText) as { detail?: unknown };
            if (typeof response.detail === "string") message = response.detail;
          } catch {
            // Storage-provider errors do not always return JSON.
          }
          reject(new ApiError(message, xhr.status));
        } else {
          resolve();
        }
      };
      xhr.send(body);
    });
  await attempt(true);
}

function hexDigest(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function base64Digest(hex: string): string {
  const bytes = hex.match(/.{2}/g) ?? [];
  return btoa(String.fromCharCode(...bytes.map((byte) => Number.parseInt(byte, 16))));
}

export async function uploadAdminBook(
  file: File,
  metadata: AdminBookUploadMetadata,
  options: {
    signal: AbortSignal;
    existingSessionId?: string;
    onSession: (sessionId: string) => void;
    onProgress: (loaded: number, total: number) => void;
  },
): Promise<{ session: AdminBookUploadSession; book: AdminBook }> {
  let session: AdminBookUploadSession;
  if (options.existingSessionId) {
    session = await request<AdminBookUploadSession>(
      `/api/admin/books/uploads/${options.existingSessionId}`,
    );
  } else {
    session = await request<AdminBookUploadSession>("/api/admin/books/uploads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...metadata,
        filename: file.name,
        content_type: file.type || "application/pdf",
        file_size: file.size,
      }),
    });
    options.onSession(session.id);
  }
  if (session.status === "completed" && session.book_id !== null) {
    return { session, book: await getAdminBook(session.book_id) };
  }
  let completedBytes = 0;
  for (let partNumber = 1; partNumber <= session.part_count; partNumber += 1) {
    const start = (partNumber - 1) * session.part_size;
    const end = Math.min(file.size, start + session.part_size);
    const partLength = end - start;
    if (session.uploaded_parts[String(partNumber)] === partLength) {
      completedBytes += partLength;
      options.onProgress(completedBytes, file.size);
      continue;
    }
    if (options.signal.aborted) throw new DOMException("Upload paused.", "AbortError");
    const part = file.slice(start, end);
    const sha256 = hexDigest(await crypto.subtle.digest("SHA-256", await part.arrayBuffer()));
    const instruction = await request<{
      url: string;
      method: "PUT";
      size: number;
      provider: "local" | "s3";
    }>(`/api/admin/books/uploads/${session.id}/parts/${partNumber}/authorize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sha256 }),
    });
    const partUrl = instruction.url.startsWith("http")
      ? instruction.url
      : `${apiUrl}${instruction.url}`;
    const partHeaders: Record<string, string> =
      instruction.provider === "local"
        ? { "X-Part-SHA256": sha256 }
        : { "x-amz-checksum-sha256": base64Digest(sha256) };
    await putPart(partUrl, part, partHeaders, options.signal, (loaded) => {
      options.onProgress(completedBytes + loaded, file.size);
    });
    completedBytes += partLength;
    options.onProgress(completedBytes, file.size);
  }
  const completed = await request<AdminBookUploadSession>(
    `/api/admin/books/uploads/${session.id}/complete`,
    { method: "POST" },
  );
  if (completed.book_id === null) {
    throw new ApiError("The PDF was uploaded but no book record was created.", 500);
  }
  return {
    session: completed,
    book: await getAdminBook(completed.book_id),
  };
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return request<DashboardOverview>("/api/dashboard/overview");
}

export function getCurricula(): Promise<CurriculumResponse> {
  return request<CurriculumResponse>("/api/curriculum");
}

export function getGrades(curriculumCode: string): Promise<CatalogResponse> {
  return request<CatalogResponse>(
    `/api/curriculum/${encodeURIComponent(curriculumCode)}/grades`,
  );
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

export function searchOfficialContent(
  query: string,
  grade?: number,
  subject?: string,
): Promise<OfficialBookSearchResult[]> {
  const params = new URLSearchParams({ q: query });
  if (grade !== undefined) params.set("grade", String(grade));
  if (subject) params.set("subject", subject);
  return request<OfficialBookSearchResult[]>(
    `/api/curriculum/search?${params}`,
  );
}

export function importOfficialBook(
  form: FormData,
): Promise<OfficialBookImportResponse> {
  return request<OfficialBookImportResponse>("/api/curriculum/books/import", {
    method: "POST",
    body: form,
  });
}

export async function registerUser(
  email: string,
  password: string,
): Promise<AuthTokenResponse> {
  const tokens = await request<AuthTokenResponse>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setAuthTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export async function loginUser(
  email: string,
  password: string,
): Promise<AuthTokenResponse> {
  const tokens = await request<AuthTokenResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setAuthTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/api/auth/me");
}

export function getUserSettings(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/auth/settings");
}

export function updateUserSettings(
  settings: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/auth/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings }),
  });
}

export async function refreshUserSession(): Promise<AuthTokenResponse> {
  const tokens = await renewAuthSession();
  if (tokens === null) {
    throw new ApiError("Your session expired. Please sign in again.", 401);
  }
  return tokens;
}

export async function logoutUser(refresh: string): Promise<void> {
  await request<{ status: string }>("/api/auth/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  setAuthTokens(null, null);
}

export function getAdminUsers(): Promise<AdminUserListResponse> {
  return request<AdminUserListResponse>("/api/auth/admin/users");
}

export function createAdminUser(input: AdminUserInput): Promise<AuthUser> {
  return request<AuthUser>("/api/auth/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function generateQuestions(
  input: GenerateRequest,
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/ai/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function getAIGenerationHistory(): Promise<AIHistoryEntry[]> {
  return request<AIHistoryEntry[]>("/api/ai/history");
}

export function getAIInsights(): Promise<AIAnalyticsSummary> {
  return request<AIAnalyticsSummary>("/api/ai/insights");
}

export function getAIRecommendations(): Promise<{
  status: string;
  items: { topic: string; type: string; recommendation: string }[];
}> {
  return request<{
    status: string;
    items: { topic: string; type: string; recommendation: string }[];
  }>("/api/ai/recommendations");
}

export function getStudyBooks(): Promise<StudyBook[]> {
  return request<StudyBook[]>("/api/study/books");
}

export function getCurriculumStudyBooks(): Promise<CurriculumStudyBook[]> {
  return request<CurriculumStudyBook[]>("/api/study/curriculum-books");
}

export function uploadStudyBook(file: File, title: string): Promise<StudyBook> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  return request<StudyBook>("/api/study/books", { method: "POST", body });
}

export function getStudyBookPdf(bookId: number): Promise<Blob> {
  return request<Blob>(`/api/study/books/${bookId}/file`);
}

export function deleteStudyBook(bookId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/study/books/${bookId}`, {
    method: "DELETE",
  });
}

export function askAboutBooks(
  bookIds: number[],
  prompt: string,
  language: "en" | "ur",
  imageData?: string | null,
  subject?: string,
  intent?: string,
  grade?: string,
  officialBookIds: number[] = [],
): Promise<StudyChatResponse> {
  return request<StudyChatResponse>("/api/study/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      book_ids: bookIds,
      official_book_ids: officialBookIds,
      prompt,
      language,
      image_data: imageData ?? null,
      subject: subject ?? "General Education",
      intent: intent ?? "explain",
      grade: grade ?? "General",
    }),
  });
}
