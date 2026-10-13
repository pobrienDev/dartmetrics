// Shared by the page tests: a minimal Response-like object for fetch stubs.
export function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) }
}
