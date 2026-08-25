"use client";

import { useState } from "react";
import { createVideo, uploadBytes } from "../lib/api";

/**
 * Upload form props.
 */
interface UploadFormProps {
  /** Invoked after a successful upload to refresh listings. */
  onUploaded: () => void;
}

/**
 * Upload form: registers the video via the API, then streams the file
 * straight to storage through the presigned PUT URL.
 *
 * @param root0 - Component props.
 * @param root0.onUploaded - Refresh callback after upload completes.
 * @returns The rendered upload form.
 */
export default function UploadForm({ onUploaded }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle form submission.
   *
   * @param event - DOM submit event.
   * @returns A promise resolving when the submit flow finishes.
   */
  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const session = await createVideo(file.name);
      await uploadBytes(session.upload.url, file);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="upload-form">
      <input
        type="file"
        accept="video/*"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        disabled={busy}
      />
      <button type="submit" disabled={!file || busy}>
        {busy ? "Uploading..." : "Upload video"}
      </button>
      {error ? <span role="alert">{error}</span> : null}
    </form>
  );
}
