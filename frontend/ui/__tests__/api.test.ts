/**
 * Unit tests for the typed API client (fetch mocked).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { createVideo, listVideos } from "../src/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createVideo", () => {
  /** Posts the JSON body and returns the parsed session. */
  it("creates an upload session", async () => {
    const fake = {
      video_id: "v1",
      upload: { url: "http://put", method: "PUT", expires_in_seconds: 900 },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(fake), { status: 201 })),
    );
    const session = await createVideo("a.mp4", 12);
    expect(session.video_id).toBe("v1");
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(call[0]).toContain("/videos");
    expect(JSON.parse(String(call[1]?.body)).filename).toBe("a.mp4");
  });

  /** Non-2xx responses raise. */
  it("throws on failure status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    );
    await expect(createVideo("a.mp4")).rejects.toThrow("create failed: 500");
  });
});

describe("listVideos", () => {
  /** Forwards the identity header to the API. */
  it("passes X-User-Id header", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ items: [] }), { status: 200 }),
        ),
    );
    await listVideos("user-9");
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect((call[1]?.headers as Record<string, string>)["X-User-Id"]).toBe("user-9");
  });
});
