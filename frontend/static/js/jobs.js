function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

let allJobs = [];
const applyStatuses = {};   // job_id -> status string
const tailorStatuses = {};  // job_id -> "tailored" | null

async function loadJobs() {
  const res = await fetch('/api/jobs');
  if (!res.ok) return;
  allJobs = await res.json();
  renderJobs(allJobs);
}

function renderJobs(jobs) {
  const noMsg = document.getElementById('no-jobs-msg');
  const table = document.getElementById('jobs-table');
  const tbody = document.getElementById('jobs-tbody');

  if (!jobs.length) {
    noMsg.style.display = '';
    table.style.display = 'none';
    noMsg.textContent = 'No jobs match your current filters.';
    return;
  }

  noMsg.style.display = 'none';
  table.style.display = '';

  tbody.innerHTML = jobs.map(job => {
    const status = applyStatuses[job.id] || '';
    const tailored = tailorStatuses[job.id] ? '<span class="status-badge tailored">tailored</span> ' : '';
    const statusBadge = status
      ? `<span class="status-badge ${status}">${status}</span>`
      : '';
    const secretBadge = (job.secret_instructions || []).length
      ? `<span class="status-badge secret" title="Secret word required: ${escHtml((job.secret_instructions||[]).join(', '))}">🔑 secret</span> `
      : '';
    const usWarning = job.us_remote === false
      ? '<span class="status-badge failed" title="May not be open to US applicants">⚠ non-US</span> '
      : '';
    return `
      <tr id="row-${job.id}">
        <td><a href="/jobs/${encodeURIComponent(job.id)}">${escHtml(job.title)}</a></td>
        <td>${escHtml(job.company)}</td>
        <td><span class="source-badge">${escHtml(job.source)}</span></td>
        <td>${(job.tags||[]).slice(0,4).map(t=>`<kbd>${escHtml(t)}</kbd>`).join(' ')}</td>
        <td class="action-btns">
          <button onclick="tailorJob('${job.id}')">Tailor</button>
          <button onclick="applyJob('${job.id}','auto')">Auto Apply</button>
          <button onclick="applyJob('${job.id}','semiauto')">Open URL</button>
        </td>
        <td>${usWarning}${secretBadge}${tailored}${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

function filterJobs() {
  const q = document.getElementById('search-input').value.toLowerCase();
  if (!q) { renderJobs(allJobs); return; }
  renderJobs(allJobs.filter(j =>
    j.title.toLowerCase().includes(q) ||
    j.company.toLowerCase().includes(q) ||
    (j.tags||[]).some(t => t.toLowerCase().includes(q))
  ));
}

async function refreshJobs() {
  const btn = document.getElementById('refresh-btn');
  const statusBar = document.getElementById('status-bar');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  statusBar.innerHTML = '<span aria-busy="true">Scraping RemoteOK and We Work Remotely…</span>';

  const res = await fetch('/api/jobs/refresh', {method: 'POST'});
  const data = await res.json();
  btn.removeAttribute('aria-busy');
  btn.disabled = false;

  if (!res.ok) {
    statusBar.innerHTML = `<span style="color:red">Error: ${escHtml(data.detail)}</span>`;
    return;
  }

  allJobs = data;
  statusBar.innerHTML = `<ins>Loaded ${data.length} jobs.</ins>`;
  renderJobs(allJobs);
}

async function tailorJob(jobId) {
  updateStatusCell(jobId, 'running', true);
  const res = await fetch(`/api/tailor/${jobId}`, {method: 'POST'});
  if (!res.ok) { updateStatusCell(jobId, 'failed'); return; }
  pollTailor(jobId);
}

function pollTailor(jobId) {
  const iv = setInterval(async () => {
    const res = await fetch(`/api/tailor/${jobId}/status`);
    const data = await res.json();
    if (data.status === 'done') {
      clearInterval(iv);
      tailorStatuses[jobId] = 'tailored';
      updateStatusCell(jobId, '');
    } else if (data.status === 'failed') {
      clearInterval(iv);
      updateStatusCell(jobId, 'failed');
    }
  }, 1500);
}

async function applyJob(jobId, mode) {
  updateStatusCell(jobId, 'pending');
  const res = await fetch(`/api/apply/${jobId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode})
  });
  if (!res.ok) { updateStatusCell(jobId, 'failed'); return; }
  if (mode === 'semiauto') { updateStatusCell(jobId, 'opened'); return; }
  pollApply(jobId);
}

function pollApply(jobId) {
  const iv = setInterval(async () => {
    const res = await fetch(`/api/apply/${jobId}/status`);
    const data = await res.json();
    if (['applied','failed','opened'].includes(data.status)) {
      clearInterval(iv);
      applyStatuses[jobId] = data.status;
      updateStatusCell(jobId, data.status);
    } else {
      updateStatusCell(jobId, 'running');
    }
  }, 2000);
}

function updateStatusCell(jobId, status, spinner=false) {
  const row = document.getElementById(`row-${jobId}`);
  if (!row) return;
  const cell = row.cells[5];
  const tailored = tailorStatuses[jobId] ? '<span class="status-badge tailored">tailored</span> ' : '';
  const badge = status ? `<span class="status-badge ${status}">${spinner ? '…' : status}</span>` : '';
  cell.innerHTML = tailored + badge;
}

document.getElementById('refresh-btn')?.addEventListener('click', refreshJobs);
document.getElementById('search-input')?.addEventListener('input', filterJobs);

loadJobs();
