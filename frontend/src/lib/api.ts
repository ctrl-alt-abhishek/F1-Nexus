// lib/api.ts
import { auth } from "./firebase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface RequestOptions extends RequestInit {
  requireAuth?: boolean;
}

export async function fetchApi<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);

  // Automatically inject Firebase ID token if the user is authenticated
  // (In dummy mode, auth is undefined so this is skipped or we mock it)
  if (auth?.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers.set("Authorization", `Bearer ${token}`);
    } catch (e) {
      console.error("Failed to get auth token", e);
    }
  } else if (!auth && options.requireAuth) {
    // We are in dummy mode, inject a dummy token so the backend doesn't reject it outright
    headers.set("Authorization", `Bearer dummy_dev_token`);
  }

  // Set default content type for JSON bodies
  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignored
    }
    throw new Error(`API Error ${response.status}: ${errorDetail}`);
  }

  // Handle empty responses (like 204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
