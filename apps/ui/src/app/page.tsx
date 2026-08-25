"use client";

import { useCallback, useEffect, useState } from "react";
import UploadForm from "../components/UploadForm";
import VideoTable from "../components/VideoTable";
import { listVideos, type Video } from "../lib/api";

/**
 * Home page: upload form plus auto-refreshing video list.
 *
 * @returns The page layout with upload and listing sections.
 */
export default function HomePage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setVideos(await listVideos("dev-user"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load videos");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <>
      <UploadForm onUploaded={refresh} />
      {error ? <p role="alert">API unreachable: {error}</p> : null}
      <section aria-label="video-list">
        <VideoTable videos={videos} />
      </section>
    </>
  );
}
