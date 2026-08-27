/**
 * Center-pane video workspace — filebar + hard-edged player for the workstation.
 * Exports `VideoWorkspace` and `VideoWorkspaceProps` (`video`, `src`, `onTimeUpdate`, `onSeek`, `error`, `onRetry`) rendering a `div.filebar.mono` header and `<video className="player">` with `background:#000` and `1px solid var(--border)` via `VideoWorkspace.css`.
 * Depends on `VideoWorkspace.css` tokens, `lib/status.ts` `formatDuration`, and an optional `useVideoStream` hook upstream; lifts `onTimeUpdate` for citation highlight and exposes `onSeek` for agent citation pills.
 */

"use client";

import React, { useRef } from "react";
import "./VideoWorkspace.css";
import { formatDuration } from "../lib/status";

/**
 * Minimal video identity accepted by the workspace.
 *
 * `filename` and `video_id` are required for the filebar, while `duration`
 * and `status` are optional and rendered only when present. Matches the
 * subset of `Video` needed for the center pane.
 */
export interface WorkspaceVideo {
  /** Original filename shown in the filebar. */
  filename: string;
  /** Video id, used by `useVideoStream` upstream and for keying. */
  video_id: string;
  /** Duration in seconds; `null` or `undefined` renders as "-". */
  duration?: number | null;
  /** Lifecycle status string (e.g. PROCESSED) shown in the filebar. */
  status?: string;
}

/**
 * Props for the centered video workspace.
 *
 * `video` may be `null` to render the empty placeholder, `src` is the
 * presigned GET URL (or `null` while loading), and `onTimeUpdate`/`onSeek`
 * wire citation highlight and seek. `error`/`onRetry` drive the retry state.
 */
export interface VideoWorkspaceProps {
  /** Selected video identity or `null`/`undefined` when no selection. */
  video?: WorkspaceVideo | null;
  /** Presigned stream URL or `null` while loading/empty. */
  src: string | null;
  /** Lifted time update invoked on every `timeupdate` event with `currentTime` seconds. */
  onTimeUpdate?: (currentTime: number) => void;
  /** Seek target in seconds; when set, the player seeks to this time. */
  seekTo?: number | null;
  /** Optional error message; when present an error state with retry is shown. */
  error?: string | null;
  /** Retry handler for the error state; refetches the presigned URL when provided. */
  onRetry?: () => void;
}

/**
 * Centered video workspace with mono filebar and boxy player.
 *
 * Renders `Select a video` when `video` or `src` is missing, a retryable
 * error when `error` is set, a loading placeholder when `video` is present
 * but `src` is still `null`, and otherwise a `div.filebar.mono` filename +
 * duration/status header plus a `<video ref>` with `controls`,
 * `background:#000`, and `border:1px solid var(--border)` that lifts
 * `onTimeUpdate` for citation highlighting and supports imperative seek via
 * `onSeek`.
 *
 * @param root0 - Component props.
 * @param root0.video - Selected video or null.
 * @param root0.src - Presigned stream URL or null.
 * @param root0.onTimeUpdate - Time update callback.
 * @param root0.onSeek - Optional seek callback.
 * @param root0.error - Optional error message.
 * @param root0.onRetry - Optional retry callback.
 * @returns The workspace element.
 */
export default function VideoWorkspace({
  video,
  src,
  onTimeUpdate = () => {},
  seekTo,
  error,
  onRetry,
}: VideoWorkspaceProps) {
  const ref = useRef<HTMLVideoElement>(null);

  React.useEffect(() => {
    if (seekTo !== null && seekTo !== undefined && ref.current) {
      ref.current.currentTime = seekTo;
    }
  }, [seekTo]);

  if (error) {
    return (
      <div className="video-workspace" data-testid="video-workspace">
        <div className="video-error" role="alert">
          <span>{error}</span>
          {onRetry ? (
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (!video) {
    return (
      <div className="video-workspace" data-testid="video-workspace">
        <div className="video-empty">Select a video</div>
      </div>
    );
  }

  if (!src) {
    return (
      <div className="video-workspace" data-testid="video-workspace">
        <div className="filebar mono">
          <span className="filename">{video.filename}</span>
          <span className="filebar-meta">
            {video.duration !== undefined
              ? formatDuration(video.duration ?? null)
              : null}
            {video.status ? ` · ${video.status}` : null}
          </span>
        </div>
        <div className="video-loading">Loading…</div>
      </div>
    );
  }

  return (
    <div className="video-workspace" data-testid="video-workspace">
      <div className="filebar mono">
        <span className="filename">{video.filename}</span>
        <span className="filebar-meta">
          {video.duration !== undefined ? formatDuration(video.duration ?? null) : null}
          {video.status ? ` · ${video.status}` : null}
        </span>
      </div>
      <video
        ref={ref}
        src={src}
        controls
        className="player"
        onTimeUpdate={(e) => onTimeUpdate(e.currentTarget.currentTime)}
      />
    </div>
  );
}
