/**
 * src/lib/api.js
 *
 * Centralized API configuration.
 *
 * In development:  calls http://localhost:8000 directly (no proxy needed)
 * In production:   uses VITE_API_URL env var
 *
 * This removes the dependency on Vite proxy being configured correctly,
 * which was causing all charts to show empty data.
 */

// Use VITE_API_URL in production; fall back to localhost:8000 in dev
export const BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");

/**
 * Generic fetch helper — throws on non-OK responses with a useful message.
 */
export async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} on ${path}: ${text || res.statusText}`);
  }
  return res.json();
}

/**
 * Safely extract an array from API responses that may be:
 *   - A plain array     (most endpoints)
 *   - Paginated object  { total, page, pages, data: [] }
 */
export function extractArray(response) {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.data)) return response.data;
  return [];
}

// ─── Pre-built query functions ────────────────────────────────────────────────

export const api = {
  summary:       () => apiFetch("/api/summary"),
  funnel:        () => apiFetch("/api/funnel"),
  insights:      () => apiFetch("/api/insights"),
  dataQuality:   () => apiFetch("/api/data-quality"),
  monthly:       (year) => apiFetch(`/api/monthly${year ? `?year=${year}` : ""}`),
  channels:      (sort) => apiFetch(`/api/channels?page_size=100${sort ? `&sort_by=${sort}&order=desc` : ""}`),
  channelDetail: (name) => apiFetch(`/api/channels/${encodeURIComponent(name)}`),
  users:         (limit = 200) => apiFetch(`/api/users?limit=${limit}`),
  inputTypes:    () => apiFetch("/api/input-types"),
  outputTypes:   () => apiFetch("/api/output-types"),
  languages:     () => apiFetch("/api/languages"),
  platforms:     (channel) => apiFetch(`/api/publishing-platforms${channel ? `?channel=${encodeURIComponent(channel)}` : ""}`),
  dimensions:    () => apiFetch("/api/dimensions"),
  multidim:      (dim1, dim2) => apiFetch(`/api/multidimensional?dim1=${dim1}&dim2=${dim2}`),
  kpis:          () => apiFetch("/api/kpis"),
  videos: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, v);
    });
    return apiFetch(`/api/videos?${q.toString()}`);
  },

  // Chat
  chatStream: (question) =>
    `${BASE_URL}/api/chat/stream?question=${encodeURIComponent(question)}`,
};
