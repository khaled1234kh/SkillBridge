// Brave ships Chromium's Web Speech API but cannot reach Google's speech
// servers, so browser STT deadlocks there. Detect it robustly: the UA token
// covers the normal case; `navigator.brave` (a public, always-present property
// Brave exposes) also covers UA-stripped or customized user agents.
export function isBraveBrowser(): boolean {
  if (typeof navigator === 'undefined') return false
  return /Brave\//i.test(navigator.userAgent || '') ||
    !!(navigator as unknown as { brave?: unknown }).brave
}