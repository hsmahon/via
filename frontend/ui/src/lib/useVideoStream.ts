/**
 * Presigned GET hook for video playback — fetches a short-lived stream URL.
 * Exports `useVideoStream(videoId)` which returns `string | null` and handles empty `videoId` → `null`, `AbortController` cleanup, and `X-User-Id` header via `API_URL` from `lib/api.ts`.
 * Consumed by `VideoWorkspace` and `page.tsx` to wire the `<video>` element to the backend `GET /videos/{id}/stream` presigned URL.
 */

"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";

/**
 * Fetch a presigned stream URL for the given video.
 *
 * Handles abort on unmount or `videoId` change and returns `null` when
 * `videoId` is empty. Uses the v0.1 `X-User-Id` header and `API_URL` from
 * `lib/api.ts`; on failure exposes `error` so callers can render retry states.
 *
 * @param videoId - Video id to presign, or `null` when no selection.
 * @param userId - Acting user id for ownership check.
 * @returns Object with `url`, `error`, and `retry` callback.
 */
export function useVideoStream(
  videoId: string | null,
  userId: string = "dev-user",
): { url: string | null; error: string | null; retry: () => void } {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!videoId) {
      setUrl(null);
      setError(null);
      return;
    }
    const ac = new AbortController();
    setUrl(null);
    setError(null);
    fetch(`${API_URL}/videos/${videoId}/stream`, {
      headers: { "X-User-Id": userId },
      signal: ac.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`stream failed: ${r.status}`);
        return r.json() as Promise<{ url: string }>;
      })
      .then((j) => {
        if (!ac.signal.aborted) setUrl(j.url);
      })
      .catch((e: unknown) => {
        if (!ac.signal.aborted) {
          setUrl(null);
          setError(e instanceof Error ? e.message : "failed to load video");
        }
      });
    return () => ac.abort();
  }, [videoId, userId, tick]);

  return { url, error, retry: () => setTick((t) => t + 1) };
}
