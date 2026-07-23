// Local File Index UI

const API = window.location.origin;

function fmtSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(2) + ' GB';
  if (bytes > 1e6) return (bytes / 1e6).toFixed(2) + ' MB';
  if (bytes > 1e3) return (bytes / 1e3).toFixed(1) + ' KB';
  return bytes + ' B';
}

function fmtDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

async function loadStats() {
  const r = await fetch(`${API}/api/files/stats`);
  const s = await r.json();
  document.getElementById('totalFiles').textContent = s.total_files.toLocaleString();
  document.getElementById('totalSize').textContent = fmtSize(s.total_bytes);
  document.getElementById('lastRun').textContent = s.last_run ? s.last_run.finished_at.slice(0, 19).replace('T', ' ') : '—';
  document.getElementById('status').textContent = 'Connected';

  const cloud = document.getElementById('extCloud');
  cloud.innerHTML = '';
  (s.extensions || []).forEach(e => {
    const tag = document.createElement('span');
    tag.className = 'ext-tag';
    tag.textContent = `${e.ext} · ${e.count}`;
    tag.onclick = () => {
      document.getElementById('ext').value = e.ext;
      doSearch();
    };
    cloud.appendChild(tag);
  });
}

async function doSearch() {
  const q = document.getElementById('search').value;
  const ext = document.getElementById('ext').value;
  const url = new URL(`${API}/api/files/search`);
  if (q) url.searchParams.set('q', q);
  if (ext) url.searchParams.set('ext', ext);
  url.searchParams.set('limit', '200');

  const r = await fetch(url);
  const data = await r.json();
  renderFiles(data.files);
}

async function loadDuplicates() {
  const r = await fetch(`${API}/api/files/duplicates?limit=200`);
  const data = await r.json();
  const rows = [];
  data.groups.forEach(g => {
    g.files.forEach(f => {
      rows.push({ ...f, dupGroup: g.sha256 });
    });
  });
  renderFiles(rows, true);
}

function renderFiles(files, showDup = false) {
  const tbody = document.getElementById('resultsBody');
  tbody.innerHTML = '';
  if (!files.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">No results</td></tr>';
    return;
  }

  files.forEach(f => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="mono" title="${f.sha256}">${f.sha256 ? f.sha256.slice(0, 12) : '—'}</td>
      <td class="num">${fmtSize(f.size)}</td>
      <td>${fmtDate(f.mtime)}</td>
      <td class="path" title="${f.path}">${f.path}</td>
      <td class="num">${f.entropy != null ? f.entropy.toFixed(2) : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById('btnSearch').onclick = doSearch;
document.getElementById('btnDups').onclick = loadDuplicates;
document.getElementById('search').onkeyup = (e) => { if (e.key === 'Enter') doSearch(); };
document.getElementById('ext').onkeyup = (e) => { if (e.key === 'Enter') doSearch(); };

loadStats().catch(e => document.getElementById('status').textContent = 'Error: ' + e.message);
