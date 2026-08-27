/**
 * Typed Via API client for the browser — video CRUD and presigned URLs.
 * Exports `API_URL`, `Video`/`CreateVideoResponse`/`StreamUrlResponse`/`AgentResponse` types and fetch helpers `createVideo`/`uploadBytes`/`listVideos`/`getVideoStreamUrl`.
 * Consumed by `useVideos`/`useVideoStream`/`VideoWorkspace`/`Library` and `page.tsx` for the 3-pane workstation with `X-User-Id` v0.1 auth.
 */

/**
 * Base URL of the Via API service.
 *
 * Defaults to `http://localhost:8080` and is overridden by
 * `NEXT_PUBLIC_API_URL` in production. Used by `createVideo`/`listVideos`
 * and `getVideoStreamUrl` for browser fetches with `X-User-Id` auth.
 */
export const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/**
 * A video as returned by the Via API.
 *
 * Includes identity (`video_id`/`user_id`/`filename`), optional `duration`,
 * and `status` lifecycle string. Lists are ordered newest-first.
 */
export interface Video {
  /** Unique identifier of the video. */
  video_id: string;
  /** Owning user id. */
  user_id: string;
  /** Original filename. */
  filename: string;
  /** Duration in seconds, when known. */
  duration: number | null;
  /** Lifecycle status (UPLOADING, PROCESSING, ...). */
  status: string;
}

/**
 * Response of POST /videos containing the upload target.
 *
 * Carries the new `video_id` and, when configured, a presigned PUT `upload`
 * target with `url`/`method`/`expires_in_seconds` for direct browser upload.
 */
export interface CreateVideoResponse {
  /** Newly created video id. */
  video_id: string;
  /** Presigned PUT target for the raw bytes. */
  upload: { url: string; method: string; expires_in_seconds: number };
}

/**
 * Create an upload session via the API.
 *
 * @param filename - Original file name to register.
 * @param duration - Optional duration in seconds.
 * @returns The created session including the presigned upload URL.
 */
export async function createVideo(
  filename: string,
  duration?: number,
): Promise<CreateVideoResponse> {
  const response = await fetch(`${API_URL}/videos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, duration }),
  });
  if (!response.ok) {
    throw new Error(`create failed: ${response.status}`);
  }
  return response.json() as Promise<CreateVideoResponse>;
}

/**
 * Upload raw bytes to the presigned URL returned by {@link createVideo}.
 *
 * @param uploadUrl - Presigned PUT url.
 * @param file - File selected by the user.
 */
export async function uploadBytes(uploadUrl: string, file: File): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type || "application/octet-stream" },
  });
  if (!response.ok) {
    throw new Error(`upload failed: ${response.status}`);
  }
}

/**
 * Fetch the acting user's videos.
 *
 * @param userId - Acting user id (v0.1 identity header).
 * @returns List of videos newest-first.
 */
export async function listVideos(userId: string): Promise<Video[]> {
  const response = await fetch(`${API_URL}/videos`, {
    headers: { "X-User-Id": userId },
  });
  if (!response.ok) {
    throw new Error(`list failed: ${response.status}`);
  }
  const body = (await response.json()) as { items: Video[] };
  return body.items;
}

/**
 * Response of GET /videos/:id/stream containing the presigned GET URL.
 *
 * Holds the short-lived `url` for `<video src>` and `expires_in_seconds`
 * until expiry. Enforces ownership before presigning on the server.
 */
export interface StreamUrlResponse {
  /** Presigned GET URL for the video object. */
  url: string;
  /** Expiry in seconds for the URL. */
  expires_in_seconds: number;
}

/**
 * Agent citation — timestamped transcript span attached to an answer.
 *
 * Carries `ts` seconds and quoted `text` grounding the answer; rendered as
 * clickable seek pills in `AgentPane` to jump the player.
 */
export interface AgentCitation {
  /** Timestamp in seconds that the citation refers to. */
  ts: number;
  /** Quoted transcript text for the citation span. */
  text: string;
}

/**
 * Response from POST /agent/invoke — answer plus optional citations.
 *
 * Contains the assistant `answer` text and, when grounding is available,
 * `citations` with `ts`/`text` for transcript seek pills.
 */
export interface AgentResponse {
  /** Assistant answer text, possibly with citation markers. */
  answer: string;
  /** Optional citations grounding the answer in transcript timestamps. */
  citations?: AgentCitation[];
}

/**
 * Fetch a presigned GET URL for video playback.
 *
 * @param videoId - Video id to presign.
 * @param userId - Acting user id (v0.1 identity header).
 * @returns Presigned URL string for the `src` of a `<video>` element.
 */
export async function getVideoStreamUrl(
  videoId: string,
  userId: string,
): Promise<string> {
  const response = await fetch(`${API_URL}/videos/${videoId}/stream`, {
    headers: { "X-User-Id": userId },
  });
  if (!response.ok) {
    throw new Error(`stream failed: ${response.status}`);
  }
  const body = (await response.json()) as StreamUrlResponse;
  return body.url;
}
