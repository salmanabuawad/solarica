const CONNECTOR = 'http://127.0.0.1:8765';
const POLL_INTERVAL_SECONDS = 5;

let state = {
  connectorOnline: false,
  connected: false,
  port: null,
  transferDetected: false,
  unsynced: 0,
  importState: 'idle',
  lastImported: 0,
  lastError: null,
};

// ── Badge helpers ────────────────────────────────────────────────
function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

function updateBadge() {
  if (!state.connectorOnline) {
    setBadge('OFF', '#ef4444');
  } else if (!state.connected) {
    setBadge('—', '#64748b');
  } else if (state.transferDetected) {
    setBadge('RX', '#22c55e');
  } else if (state.unsynced > 0) {
    setBadge(state.unsynced > 99 ? '99+' : String(state.unsynced), '#f59e0b');
  } else {
    setBadge('OK', '#22c55e');
  }
}

// ── Fetch connector ──────────────────────────────────────────────
async function fetchConnector(path, opts = {}) {
  const r = await fetch(CONNECTOR + path, { ...opts, signal: AbortSignal.timeout(4000) });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

// ── Poll loop ────────────────────────────────────────────────────
async function poll() {
  try {
    const [health, device, importStatus] = await Promise.all([
      fetchConnector('/health'),
      fetchConnector('/api/device/status'),
      fetchConnector('/api/import/status'),
    ]);

    const prevUnsynced = state.unsynced;
    const prevImported = state.lastImported;

    state = {
      connectorOnline:  true,
      connected:        device.connected,
      port:             device.port,
      transferDetected: device.transferModeDetected,
      unsynced:         importStatus.unsyncedCount ?? 0,
      importState:      importStatus.state,
      lastImported:     importStatus.lastImportedCount ?? 0,
      lastError:        device.lastError,
      version:          health.version,
      runtime:          health.runtime,
    };

    // Notify if new measurements were captured
    if (state.lastImported > prevImported && prevImported >= 0) {
      const n = state.lastImported - prevImported;
      chrome.notifications.create('import_done_' + Date.now(), {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: 'Solarica — Measurements Captured',
        message: `${state.lastImported} measurement(s) imported from PVPM. ${state.unsynced} waiting to sync.`,
        priority: 1,
      });
    }

  } catch {
    state.connectorOnline = false;
    state.connected = false;
  }

  updateBadge();
  broadcastToContent(state);
}

// ── Broadcast state to all solarica.wavelync.com tabs ────────────
function broadcastToContent(payload) {
  chrome.tabs.query({ url: 'https://solarica.wavelync.com/*' }, tabs => {
    tabs.forEach(tab => {
      chrome.tabs.sendMessage(tab.id, { type: 'CONNECTOR_STATE', payload }).catch(() => {});
    });
  });
}

// ── Message handler (from popup & content scripts) ────────────────
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type === 'GET_STATE') {
    reply(state);
    return true;
  }

  if (msg.type === 'CONNECT') {
    fetchConnector('/api/device/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: msg.port || 'auto' }),
    })
      .then(d => { reply({ ok: true, data: d }); poll(); })
      .catch(e => reply({ ok: false, error: e.message }));
    return true;
  }

  if (msg.type === 'DISCONNECT') {
    fetchConnector('/api/device/disconnect', { method: 'POST' })
      .then(() => { reply({ ok: true }); poll(); })
      .catch(e => reply({ ok: false, error: e.message }));
    return true;
  }

  if (msg.type === 'READ') {
    fetchConnector('/api/import/start', { method: 'POST' })
      .then(r => reply({ ok: true, data: r }))
      .catch(e => reply({ ok: false, error: e.message }));
    return true;
  }

  if (msg.type === 'SYNC') {
    fetchConnector('/api/sync/upload', { method: 'POST' })
      .then(r => { reply({ ok: true, data: r }); poll(); })
      .catch(e => reply({ ok: false, error: e.message }));
    return true;
  }

  if (msg.type === 'GET_PORTS') {
    fetchConnector('/api/device/ports')
      .then(r => reply({ ok: true, data: r }))
      .catch(e => reply({ ok: false, error: e.message }));
    return true;
  }
});

// ── Alarm for periodic polling ────────────────────────────────────
chrome.alarms.create('poll', { periodInMinutes: POLL_INTERVAL_SECONDS / 60 });
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'poll') poll(); });

// Initial poll on startup
poll();
