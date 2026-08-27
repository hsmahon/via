import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ subsets: ["latin"] });
const geistMono = Geist_Mono({ subsets: ["latin"] });

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
    <html lang="en" className={`${geistSans.className} ${geistMono.className}`}>
      <body className={geistSans.className}>{children}</body>
    </html>
  );
}
