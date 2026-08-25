import { formatDuration, statusColor } from "../lib/status";
import type { Video } from "../lib/api";

/**
 * Video table props.
 */
interface VideoTableProps {
  /** Videos to display, newest first. */
  videos: Video[];
}

/**
 * Table of videos with live status chips.
 *
 * @param root0 - Component props.
 * @param root0.videos - Videos to render.
 * @returns The rendered table (or empty-state text).
 */
export default function VideoTable({ videos }: VideoTableProps) {
  if (videos.length === 0) {
    return <p>No videos yet. Upload one to get started.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>File</th>
          <th>Status</th>
          <th>Duration</th>
        </tr>
      </thead>
      <tbody>
        {videos.map((video) => (
          <tr key={video.video_id}>
            <td>{video.filename}</td>
            <td>
              <span style={{ color: statusColor(video.status), fontWeight: 600 }}>
                {video.status}
              </span>
            </td>
            <td>{formatDuration(video.duration)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
