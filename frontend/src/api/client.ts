import type { ApiErrorBody } from '../types'

/** Any failed or unparseable API response, with the backend's real
 * `status`, `code` and `message`. Components render `message` directly. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** True when the ticket no longer exists (renders the 404 state). */
  get isNotFound(): boolean {
    return this.status === 404
  }
}

/** True for API errors; anything else (a bug) is not shown as one. */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/** Human message for any thrown value, for ErrorBanner. */
export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Could not reach the SupportIQ API')
  }

  // Parse whatever came back: error envelopes and success bodies are
  // both JSON; a non-JSON body is an unexpected response, not a crash.
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const envelope = (payload as ApiErrorBody | null)?.error
    if (envelope && typeof envelope.message === 'string') {
      throw new ApiError(response.status, envelope.code, envelope.message)
    }
    throw new ApiError(
      response.status,
      'UNEXPECTED_RESPONSE',
      `Unexpected API response (HTTP ${response.status})`,
    )
  }

  if (payload === null) {
    throw new ApiError(
      response.status,
      'UNEXPECTED_RESPONSE',
      'The API returned a response that is not valid JSON',
    )
  }
  return payload as T
}

export const api = {
  get: <T>(path: string): Promise<T> => request<T>(path),
  post: <T>(path: string, body: unknown): Promise<T> =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown): Promise<T> =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
}
