let state = null;

function send(type, data = {}) {
  return new Promise(resolve =>
    chrome.runtime.sendMessage({ type, ...data }, resolve)
  );
}

function setMsg(text, color = 'var(--green)') {
  const el = document.getElementById('msg');
  el.style.color = color;
  el.textContent = text;
  setTimeout(() => { el.textContent = ''; }, 3000);
}

function setLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  btn.disabled = loading;
  btn.innerHTML = loading ? '<span class="spin"></span>' : label;
}

function render(s) {
  state = s;

  const online = s.connectorOnline;
  document.getElementById('offlineMsg').style.display = online ? 'none' : '';
  document.getElementById('mainContent').style.display = online ? '' : 'none';

  const hdr = document.getElementById('hdrBadge');
  if (!online) {
    hdr.className = 'badge red';
    hdr.innerHTML = '<div class="dot"></div> Offline';
    return;
  }

  hdr.className = s.connected ? 'badge green' : 'badge gray';
  hdr.innerHTML = `<div class="dot"></div> ${s.connected ? 'Connected' : 'Online'}`;

  document.getElementById('devModel').textContent = 'PVPM 1540X';
  document.getElementById('devPort').textContent  = s.port || '—';

  const connEl = document.getElementById('devConn');
  connEl.textContent  = s.connected ? 'Yes' : 'No';
  connEl.className    = 'val ' + (s.connected ? 'good' : 'bad');

  document.getElementById('btnConn').disabled = s.connected;
  document.getElementById('btnDisc').disabled = !s.connected;

  const pill  = document.getElementById('transferPill');
  const icon  = document.getElementById('transferIcon');
  const label = document.getElementById('transferLabel');
  if (s.transferDetected) {
    pill.className = 'transfer-pill active';
    icon.textContent = '✅';
    label.textContent = 'Transfer Mode Active';
    label.style.color = 'var(--green)';
  } else {
    pill.className = 'transfer-pill waiting';
    icon.textContent = '📡';
    label.textContent = s.connected ? 'Press Transfer on device' : 'Not connected';
    label.style.color = '';
  }

  const unsynced = document.getElementById('unsyncedNum');
  unsynced.textContent = s.unsynced ?? '—';
  unsynced.className = 'num ' + (s.unsynced > 0 ? 'warn' : 'good');

  document.getElementById('lastPoll').textContent =
    'Updated ' + new Date().toLocaleTimeString();
}

async function loadPorts() {
  const r = await send('GET_PORTS');
  if (!r?.ok) return;
  const sel = document.getElementById('portSel');
  sel.innerHTML = '<option value="auto">Auto-detect port</option>';
  (r.data?.items || []).forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.name;
    opt.textContent = `${p.name} — ${p.description}`;
    sel.appendChild(opt);
  });
}

async function connectDev() {
  const port = document.getElementById('portSel').value;
  setLoading('btnConn', true, 'Connect');
  const r = await send('CONNECT', { port });
  setLoading('btnConn', false, 'Connect');
  if (r?.ok) {
    setMsg(`Connected on ${r.data?.port}`);
    refresh();
  } else {
    setMsg('Connect failed: ' + r?.error, 'var(--red)');
  }
}

async function disconnectDev() {
  setLoading('btnDisc', true, 'Disconnect');
  await send('DISCONNECT');
  setLoading('btnDisc', false, 'Disconnect');
  setMsg('Disconnected');
  refresh();
}

async function readDevice() {
  setLoading('btnRead', true, '⬇ Read from Device');
  const r = await send('READ');
  setLoading('btnRead', false, '⬇ Read from Device');
  if (r?.ok) {
    setMsg('Reading… press Transfer on PVPM now');
  } else {
    setMsg('Failed: ' + r?.error, 'var(--red)');
  }
}

async function syncCloud() {
  setLoading('btnSync', true, '↑ Sync to Cloud');
  const r = await send('SYNC');
  setLoading('btnSync', false, '↑ Sync to Cloud');
  if (r?.ok) {
    const d = r.data;
    setMsg(`Synced ${d?.uploaded ?? 0} · failed ${d?.failed ?? 0}`);
    refresh();
  } else {
    setMsg('Sync failed: ' + r?.error, 'var(--red)');
  }
}

function openUI() {
  chrome.tabs.create({ url: 'http://127.0.0.1:8765' });
}

async function refresh() {
  const s = await send('GET_STATE');
  if (s) render(s);
}

(async () => {
  await loadPorts();
  await refresh();
  setInterval(refresh, 3000);
})();
