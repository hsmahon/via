import type { NextConfig } from "next";

/**
 * Next.js configuration for the Via UI shell.
 *
 * `output: "standalone"` produces a minimal server bundle for the Docker
 * image; API calls are proxied client-side via NEXT_PUBLIC_API_URL.
 */
const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
