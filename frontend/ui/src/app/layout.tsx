import type { Metadata } from "next";
import "./globals.css";

/** Root HTML shell for the Via UI. */
export const metadata: Metadata = {
  title: "Via - Video Intelligence",
  description: "Upload a video, then talk to an agent that understands it.",
};

/**
 * Application layout.
 *
 * @param root0 - Component props.
 * @param root0.children - Children rendered into the body.
 * @returns The root html document structure.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "system-ui" }}>
          <h1>Via</h1>
          <p>Video intelligence agent</p>
          {children}
        </main>
      </body>
    </html>
  );
}
