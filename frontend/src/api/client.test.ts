import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, clearToken, setToken } from './client'

function mockFetch(status: number, body: unknown) {
  const response = {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }
  const spy = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', spy)
  return spy
}

describe('api client', () => {
  beforeEach(() => clearToken())
  afterEach(() => {
    vi.unstubAllGlobals()
    clearToken()
  })

  it('returns parsed JSON on success', async () => {
    mockFetch(200, { status: 'ok' })
    await expect(api('/api/v1/health')).resolves.toEqual({ status: 'ok' })
  })

  it('attaches the bearer token when one is stored', async () => {
    setToken('token-123')
    const spy = mockFetch(200, {})
    await api('/api/v1/me')
    const [, options] = spy.mock.calls[0]
    expect(options.headers['Authorization']).toBe('Bearer token-123')
  })

  it('sends no auth header when signed out', async () => {
    const spy = mockFetch(200, {})
    await api('/api/v1/health')
    const [, options] = spy.mock.calls[0]
    expect(options.headers['Authorization']).toBeUndefined()
  })

  it('turns the backend error envelope into a typed ApiError', async () => {
    mockFetch(409, {
      error: { code: 'EMAIL_ALREADY_REGISTERED', message: 'Taken.' },
    })
    const failure = api('/api/v1/auth/register', { method: 'POST', body: {} })
    await expect(failure).rejects.toMatchObject({
      status: 409,
      code: 'EMAIL_ALREADY_REGISTERED',
      message: 'Taken.',
    })
    await expect(failure).rejects.toBeInstanceOf(ApiError)
  })

  it('maps FastAPI 422 validation bodies to VALIDATION_ERROR', async () => {
    mockFetch(422, { detail: [{ loc: ['body', 'email'] }] })
    await expect(api('/x', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
    })
  })

  it('survives a non-JSON error body', async () => {
    const response = {
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error('not json')),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(api('/x')).rejects.toMatchObject({ status: 502, code: 'UNKNOWN' })
  })
})
