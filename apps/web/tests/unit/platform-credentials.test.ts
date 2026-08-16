// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlatformCredentialsWorkspace } from "@/components/settings/platform-credentials-workspace";
import {
  clearMockPlatformCredentialState,
  getPlatformCredentialSettings,
  removePlatformCredentials,
  updatePlatformCredentials,
} from "@/lib/api/platform-credentials";

vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn(),
  mockApiEnabled: true,
}));

(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

type Rendered = { container: HTMLDivElement; root: Root };

function renderWorkspace(): Rendered {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  act(() => root.render(createElement(PlatformCredentialsWorkspace)));
  return { container, root };
}

async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

afterEach(() => {
  clearMockPlatformCredentialState();
  document.body.innerHTML = "";
});

describe("platform credential settings", () => {
  it("lists all seven platforms and never returns submitted secret values", async () => {
    const initial = await getPlatformCredentialSettings();
    expect(initial.platforms.map((item) => item.platform)).toEqual([
      "instagram",
      "linkedin",
      "reddit",
      "threads",
      "tiktok",
      "x",
      "youtube",
    ]);

    const updated = await updatePlatformCredentials("youtube", {
      api_key: "youtube-secret-value",
    });
    expect(JSON.stringify(updated)).not.toContain("youtube-secret-value");
    expect(updated.fields).toEqual([
      expect.objectContaining({ key: "api_key", configured: true }),
    ]);

    const removed = await removePlatformCredentials("youtube");
    expect(removed.fields).toEqual([
      expect.objectContaining({ key: "api_key", configured: false }),
    ]);
  });

  it("renders the security boundary and configured-state workflow", async () => {
    const { container, root } = renderWorkspace();
    await flush();

    expect(container.textContent).toContain("平台凭证");
    expect(container.textContent).toContain("配置不等于授权调用");
    expect(
      container.querySelectorAll('[data-testid^="platform-credential-row-"]'),
    ).toHaveLength(7);
    const secretInputs = [...container.querySelectorAll("input")];
    expect(secretInputs.every((input) => input.type === "password")).toBe(true);

    act(() => root.unmount());
  });
});
