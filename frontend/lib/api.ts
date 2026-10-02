export type Curriculum = {
  id: string;
  name: string;
  grades: string[];
};

export type CurriculumResponse = {
  curricula: Curriculum[];
};

export type HealthResponse = {
  status: string;
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
};

export type GenerateResponse = {
  status: string;
  request: GenerateRequest & { count: number; difficulty: string; language: string };
  items: unknown[];
  message: string;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, init);
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

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export function getCurricula(): Promise<CurriculumResponse> {
  return request<CurriculumResponse>('/api/curriculum');
}

export function generateQuestions(input: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>('/api/ai/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}