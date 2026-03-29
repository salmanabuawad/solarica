/**
 * Content script — injected into solarica.wavelync.com
 * Receives connector state from the background worker and
 * dispatches it as a custom DOM event so the React app can consume it.
 */

// Forward connector state to the page via a custom event
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'CONNECTOR_STATE') {
    window.dispatchEvent(
      new CustomEvent('solarica:connector', { detail: msg.payload })
    );
  }
});

// Let the page send commands back through the extension
window.addEventListener('solarica:cmd', async (e) => {
  const { type, payload } = e.detail || {};
  if (!type) return;
  const result = await chrome.runtime.sendMessage({ type, ...payload });
  window.dispatchEvent(
    new CustomEvent('solarica:cmd:result', { detail: { type, result } })
  );
});

// Announce extension presence to the page immediately
window.dispatchEvent(new CustomEvent('solarica:extension', { detail: { version: '1.0.0' } }));

// Request current state from background on load
chrome.runtime.sendMessage({ type: 'GET_STATE' }, (state) => {
  if (state) {
    window.dispatchEvent(
      new CustomEvent('solarica:connector', { detail: state })
    );
  }
});
