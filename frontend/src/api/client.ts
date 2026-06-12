const BASE_URL =
  import.meta.env.VITE_API_URL?.replace(/\/+$/, "") ?? "/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/**
 * Core fetch wrapper.
 *
 * Auth model (P5-T3): the access token lives in an httpOnly cookie set by the
 * backend, NOT in localStorage (which is XSS-readable). We never inject an
 * Authorization header; instead `credentials: "include"` makes the browser
 * attach the cookie on same-origin requests. On 401 we redirect to /login.
 * - Returns parsed JSON for all non-204 responses.
 */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(url, { ...options, headers, credentials: "include" });

  if (res.status === 401) {
    // Only redirect when running in a browser context (not during tests).
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

/**
 * Raw fetch wrapper that returns the full Response object.
 * Useful for binary downloads (CSV, images) where the caller needs
 * access to headers and blob/text data.
 */
async function requestRaw(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(url, { ...options, headers, credentials: "include" });

  if (res.status === 401) {
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res;
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, data?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),

  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  /** Returns the raw Response (for binary / streaming downloads). */
  getRaw: (path: string) => requestRaw(path),
};

export { ApiError, BASE_URL };
