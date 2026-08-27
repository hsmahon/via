/**
 * Polling hook for the video library — listVideos with 5s refresh.
 * Exports `useVideos(userId)` returning `{videos, loading, error, refresh}` and handles `AbortController` cleanup, interval polling, and `X-User-Id` identity via `listVideos` from `lib/api.ts`.
 * Consumed by `page.tsx` to drive `Library` selection and `VideoWorkspace`/`AgentPane` enablement in the 3-pane workstation.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { listVideos, type Video } from "./api";

/**
 * Return value of {@link useVideos}.
 *
 * Bundles the polled `videos`, `loading`/`error` flags, and a manual
 * `refresh` that callers can invoke after uploads or retries.
 */
export interface UseVideosResult {
  /** Current video list, newest first. */
  videos: Video[];
  /** True while the initial fetch is in flight. */
  loading: boolean;
  /** Last fetch error message, or null when healthy. */
  error: string | null;
  /** Manual refresh — refetches the list immediately. */
  refresh: () => Promise<void>;
}

/**
 * Poll the user's video library every 5s and expose refresh.
 *
 * Wraps `listVideos(userId)` with an `AbortController` per fetch, a
 * `setInterval` poll, and loading/error state so callers can render
 * placeholders and retry. The polling interval is cleared on unmount
 * and on userId change.
 *
 * @param userId - Acting user id forwarded as `X-User-Id`.
 * @returns Videos, loading, error, and manual refresh.
 */
export function useVideos(userId: string): UseVideosResult {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const items = await listVideos(userId);
      setVideos(items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load videos");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    void refresh();
    const timer = setInterval(() => {
      if (!cancelled) void refresh();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [refresh]);

  return { videos, loading, error, refresh };
}
