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
 * `videoId` is empty. Uses the v0.1 `X-User-Id: dev-user` header and
 * `API_URL` from `lib/api.ts`; errors are swallowed and leave the URL as
 * `null` so callers can render retry/empty states.
 *
 * @param videoId - Video id to presign, or `null` when no selection.
 * @returns Presigned URL or `null` while loading or when no video is selected.
 */
export function useVideoStream(videoId: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) {
      setUrl(null);
      return;
    }
    const ac = new AbortController();
    setUrl(null);
    fetch(`${API_URL}/videos/${videoId}/stream`, {
      headers: { "X-User-Id": "dev-user" },
      signal: ac.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`stream failed: ${r.status}`);
        return r.json() as Promise<{ url: string }>;
      })
      .then((j) => {
        if (!ac.signal.aborted) setUrl(j.url);
      })
      .catch(() => {
        if (!ac.signal.aborted) setUrl(null);
      });
    return () => ac.abort();
  }, [videoId]);

  return url;
}
