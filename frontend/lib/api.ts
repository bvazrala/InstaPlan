// REST client for the FastAPI backend. Every request carries the user's token; the server decides what they may see.
import { getAccessToken } from "./supabase";

import { API_URL } from "./config";
export { API_URL } from "./config";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
