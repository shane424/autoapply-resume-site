// Popup script
const DEFAULT_SERVER = 'http://localhost:8000';
let currentJobData = null;

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
  });
});

async function loadSavedData() {
  const data = await chrome.storage.local.get(['serverUrl', 'userProfile', 'baseResume', 'stats']);

  document.getElementById('serverUrl').value = data.serverUrl || DEFAULT_SERVER;

  if (data.userProfile) {
    const p = data.userProfile;
    ['firstName','lastName','email','phone','address','city','state','zip','linkedin','website']
      .forEach(k => { document.getElementById(k).value = p[k] || ''; });
  }

  if (data.baseResume) document.getElementById('baseResume').value = data.baseResume;
  if (data.stats) updateStats(data.stats);

  loadCurrentJob();
}

// ── Tailor Tab ────────────────────────────────────────────────────────────────

async function loadCurrentJob() {
  const jobInfoEl = document.getElementById('job-info-card');
  const tailorBtn = document.getElementById('tailor-btn');

  jobInfoEl.innerHTML = '<p class="detecting-msg">Detecting job on current page…</p>';
  tailorBtn.style.display = 'none';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) { showNoJob(); return; }

    chrome.tabs.sendMessage(tab.id, { action: 'getJobData' }, (resp) => {
      if (chrome.runtime.lastError || !resp) { showNoJob(); return; }

      const jd = resp.jobData;
      if (jd && jd.description && jd.description.length > 100) {
        currentJobData = jd;
        jobInfoEl.innerHTML = `
          <div class="job-card">
            <div class="job-title">${escHtml(jd.title || 'Job Posting')}</div>
            ${jd.company ? `<div class="job-company">${escHtml(jd.company)}</div>` : ''}
          </div>`;
        tailorBtn.style.display = 'block';
      } else {
        showNoJob();
      }
    });
  } catch {
    showNoJob();
  }
}

function showNoJob() {
  document.getElementById('job-info-card').innerHTML = `
    <p class="detecting-msg">
      No job detected on this page.<br>
      Navigate to a job listing and reopen the popup.
    </p>`;
  document.getElementById('tailor-btn').style.display = 'none';
}

document.getElementById('tailor-btn').addEventListener('click', async () => {
  if (!currentJobData) return;

  const tailorBtn = document.getElementById('tailor-btn');
  const loadingEl = document.getElementById('tailor-loading');
  const resultEl  = document.getElementById('tailor-result');

  tailorBtn.disabled = true;
  tailorBtn.textContent = 'Tailoring…';
  loadingEl.style.display = 'block';
  resultEl.innerHTML = '';

  try {
    const { baseResume, serverUrl } = await chrome.storage.local.get(['baseResume', 'serverUrl']);
    const base = (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');

    const res = await fetch(`${base}/api/tailor/inline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text:     baseResume || '',
        job_title:       currentJobData.title       || '',
        job_company:     currentJobData.company     || '',
        job_description: currentJobData.description || '',
        job_url:         currentJobData.url         || '',
      }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Server error ${res.status}`);
    }

    const data = await res.json();

    // Track stats
    const { stats = {} } = await chrome.storage.local.get(['stats']);
    stats.resumesOptimized = (stats.resumesOptimized || 0) + 1;
    stats.totalMatchScore  = (stats.totalMatchScore  || 0) + (data.match_score || 0);
    stats.matchScoreCount  = (stats.matchScoreCount  || 0) + 1;
    await chrome.storage.local.set({ stats });

    loadingEl.style.display = 'none';
    tailorBtn.disabled = false;
    tailorBtn.textContent = 'Tailor Again';

    const kws = (data.keywords_added || [])
      .map(k => `<span class="kw-chip">${escHtml(k)}</span>`).join('');

    resultEl.innerHTML = `
      <div class="result-box">
        <div class="result-score">
          <span class="score-num">${data.match_score || 0}%</span>
          <span class="score-label">JD match</span>
        </div>
        ${kws ? `<div class="kw-chips">${kws}</div>` : ''}
        <button id="copy-resume-btn" class="btn btn-primary">Copy Resume Text</button>
        ${data.cover_letter ? '<button id="copy-cover-btn" class="btn btn-outline">Copy Cover Letter</button>' : ''}
        ${data.pdf_path ? `<p class="pdf-note" title="${escHtml(data.pdf_path)}">📄 ${escHtml(data.pdf_path.split(/[\\/]/).slice(-2).join('\\'))}</p>` : ''}
      </div>`;

    document.getElementById('copy-resume-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(data.resume_text || '').then(() => {
        const btn = document.getElementById('copy-resume-btn');
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy Resume Text'; }, 2000);
      });
    });

    document.getElementById('copy-cover-btn')?.addEventListener('click', () => {
      navigator.clipboard.writeText(data.cover_letter || '').then(() => {
        const btn = document.getElementById('copy-cover-btn');
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy Cover Letter'; }, 2000);
      });
    });

  } catch (err) {
    loadingEl.style.display = 'none';
    tailorBtn.disabled = false;
    tailorBtn.textContent = 'Tailor Resume for This Job';
    resultEl.innerHTML = `<div class="status-msg error">${escHtml(err.message)}</div>`;
  }
});

// ── Autofill ──────────────────────────────────────────────────────────────────

document.getElementById('autofill-btn').addEventListener('click', async () => {
  const btn = document.getElementById('autofill-btn');
  const statusEl = document.getElementById('autofill-status');

  btn.disabled = true;
  btn.textContent = 'Filling…';
  statusEl.innerHTML = '';

  try {
    const { serverUrl } = await chrome.storage.local.get(['serverUrl']);
    const base = (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');

    const res = await fetch(`${base}/api/profile`);
    if (!res.ok) throw new Error(`Could not load profile (${res.status}). Make sure the server is running.`);
    const profile = await res.json();

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error('No active tab found.');

    chrome.tabs.sendMessage(tab.id, { action: 'autofill', profile }, (resp) => {
      btn.disabled = false;
      btn.textContent = 'Autofill Form Fields';

      if (chrome.runtime.lastError || !resp) {
        showStatus('autofill-status', 'Could not reach the page. Try reloading the tab.', 'error');
        return;
      }
      const n = resp.filled || 0;
      if (n > 0) {
        showStatus('autofill-status', `Filled ${n} field${n !== 1 ? 's' : ''}!`, 'success');
        // Update stats
        chrome.storage.local.get(['stats']).then(({ stats = {} }) => {
          stats.formsAutofilled = (stats.formsAutofilled || 0) + 1;
          chrome.storage.local.set({ stats });
        });
      } else {
        showStatus('autofill-status', 'No matching fields found on this page.', 'error');
      }
    });
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Autofill Form Fields';
    showStatus('autofill-status', escHtml(err.message), 'error');
  }
});

// ── Server settings ───────────────────────────────────────────────────────────

document.getElementById('saveServer').addEventListener('click', async () => {
  const url = document.getElementById('serverUrl').value.trim() || DEFAULT_SERVER;
  await chrome.storage.local.set({ serverUrl: url });

  showStatus('serverStatus', 'Testing connection…', 'success');
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/api/health`);
    const data = await res.json();
    if (data.status === 'ok' || data.status === 'degraded') {
      showStatus('serverStatus', `Connected! Server is ${data.status}.`, 'success');
    } else {
      showStatus('serverStatus', 'Server responded but returned unexpected status.', 'error');
    }
  } catch {
    showStatus('serverStatus', 'Could not connect. Make sure the server is running.', 'error');
  }
});

// ── Profile ───────────────────────────────────────────────────────────────────

document.getElementById('saveProfile').addEventListener('click', async () => {
  const profile = {};
  ['firstName','lastName','email','phone','address','city','state','zip','linkedin','website']
    .forEach(k => { profile[k] = document.getElementById(k).value; });
  await chrome.storage.local.set({ userProfile: profile });
  showStatus('profileStatus', 'Profile saved!', 'success');
});

// ── Resume ────────────────────────────────────────────────────────────────────

document.getElementById('resumeFile').addEventListener('change', (e) => {
  const file = e.target.files[0];
  document.getElementById('fileName').textContent = file ? file.name : 'No file selected';
});

document.getElementById('uploadResume').addEventListener('click', async () => {
  const file = document.getElementById('resumeFile').files[0];
  if (!file) { showStatus('uploadStatus', 'Choose a PDF or DOCX file first.', 'error'); return; }

  const { serverUrl } = await chrome.storage.local.get(['serverUrl']);
  const base = (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');

  showStatus('uploadStatus', 'Uploading…', 'success');
  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${base}/api/resume/upload`, { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Server error ${res.status}`);
    }
    showStatus('uploadStatus', `Uploaded! Server parsed "${file.name}".`, 'success');
  } catch (err) {
    showStatus('uploadStatus', `Upload failed: ${err.message}`, 'error');
  }
});

document.getElementById('saveResume').addEventListener('click', async () => {
  const resume = document.getElementById('baseResume').value;
  if (!resume.trim()) { showStatus('resumeStatus', 'Please paste your resume text.', 'error'); return; }
  await chrome.storage.local.set({ baseResume: resume });
  showStatus('resumeStatus', 'Resume text saved!', 'success');
});

// ── Job Boards ────────────────────────────────────────────────────────────────

document.getElementById('open-dashboard').addEventListener('click', async (e) => {
  e.preventDefault();
  const { serverUrl } = await chrome.storage.local.get(['serverUrl']);
  const url = (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');
  chrome.tabs.create({ url });
});

// ── Stats ─────────────────────────────────────────────────────────────────────

document.getElementById('clearStats').addEventListener('click', async () => {
  if (!confirm('Reset all statistics?')) return;
  const empty = { jobsViewed: 0, resumesOptimized: 0, formsAutofilled: 0, totalMatchScore: 0, matchScoreCount: 0 };
  await chrome.storage.local.set({ stats: empty });
  updateStats(empty);
});

function updateStats(stats) {
  document.getElementById('statsJobsViewed').textContent       = stats.jobsViewed || 0;
  document.getElementById('statsResumesOptimized').textContent = stats.resumesOptimized || 0;
  document.getElementById('statsFormsAutofilled').textContent  = stats.formsAutofilled || 0;
  const avg = stats.matchScoreCount > 0
    ? Math.round(stats.totalMatchScore / stats.matchScoreCount)
    : 0;
  document.getElementById('statsAvgScore').textContent = avg + '%';
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function showStatus(elId, msg, type) {
  const el = document.getElementById(elId);
  el.innerHTML = `<div class="status-msg ${type}">${msg}</div>`;
  setTimeout(() => { el.innerHTML = ''; }, 4000);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

chrome.storage.onChanged.addListener((changes, ns) => {
  if (ns === 'local' && changes.stats) updateStats(changes.stats.newValue);
});

loadSavedData();
