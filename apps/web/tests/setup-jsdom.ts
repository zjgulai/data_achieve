/**
 * Vitest jsdom setup file.
 *
 * Node.js 26 ships an experimental Web Storage API that exposes localStorage
 * as undefined when --localstorage-file is not set. When vitest populates the
 * jsdom global, Node's undefined localStorage shadows the real jsdom Proxy.
 *
 * Fix: recover the real jsdom localStorage from window.jsdom (which vitest
 * attaches) and restore it on window so vi.spyOn(Storage.prototype, …) works.
 */

if (typeof window !== "undefined" && window.localStorage == null) {
  // vitest attaches the JSDOM instance as window.jsdom
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const jsdomInstance = (window as any).jsdom;
  if (jsdomInstance?.window?.localStorage != null) {
    // Restore the real jsdom localStorage
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      enumerable: true,
      get: () => jsdomInstance.window.localStorage,
    });
  }
}
