// Typed fetch wrapper for the DartMetrics API.
//
// The bearer token lives in localStorage so a page refresh keeps the
// session. Tokens expire server-side (ACCESS_TOKEN_EXPIRE_MINUTES); when
// any request comes back 401 the token is dropped and a
// SESSION_EXPIRED_EVENT is dispatched so the auth context can sign the
// user out and the router can bounce them to login, which sends them
// back to the page they were on afterwards.

import type { ApiErrorBody } from './types'

const TOKEN_KEY = 'dartmetrics_token'
export const SESSION_EXPIRED_EVENT = 'dartmetrics:session-expired'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** Error carrying the backend's machine-readable code (e.g. INVALID_CREDENTIALS). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    let code = 'UNKNOWN'
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as ApiErrorBody & { detail?: unknown }
      if (body.error) {
        code = body.error.code
        message = body.error.message
      } else if (body.detail) {
        // FastAPI validation errors (422) use {"detail": [...]}
        code = 'VALIDATION_ERROR'
        message = 'Please check the highlighted fields.'
      }
    } catch {
      /* non-JSON body; keep defaults */
    }
    if (response.status === 401 && getToken() !== null) {
      // The stored token no longer works (expired, or the account was
      // deactivated). Sign out app-wide rather than surfacing the raw
      // error on whatever screen made the request.
      clearToken()
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    }
    throw new ApiError(response.status, code, message)
  }

  return (await response.json()) as T
}
