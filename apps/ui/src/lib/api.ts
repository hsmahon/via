/** Base URL of the Via API service. */
export const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/** A video as returned by the Via API. */
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

/** Response of POST /videos containing the upload target. */
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
