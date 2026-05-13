// Popup script
const DEFAULT_SERVER = 'http://localhost:8000';

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
}

// Server — save and test
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
    showStatus('serverStatus',
      'Could not connect. Start the server: uvicorn app.main:app --reload --port 8000',
      'error');
  }
});

// Profile — save
document.getElementById('saveProfile').addEventListener('click', async () => {
  const profile = {};
  ['firstName','lastName','email','phone','address','city','state','zip','linkedin','website']
    .forEach(k => { profile[k] = document.getElementById(k).value; });
  await chrome.storage.local.set({ userProfile: profile });
  showStatus('profileStatus', 'Profile saved!', 'success');
});

// Resume — file name display
document.getElementById('resumeFile').addEventListener('change', (e) => {
  const file = e.target.files[0];
  document.getElementById('fileName').textContent = file ? file.name : 'No file selected';
});

// Resume — upload PDF/DOCX to server
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

// Resume — save text
document.getElementById('saveResume').addEventListener('click', async () => {
  const resume = document.getElementById('baseResume').value;
  if (!resume.trim()) { showStatus('resumeStatus', 'Please paste your resume text.', 'error'); return; }
  await chrome.storage.local.set({ baseResume: resume });
  showStatus('resumeStatus', 'Resume text saved!', 'success');
});

// Server tab — tailor resume for the current tab's page
document.getElementById('tailorCurrentPage').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { showStatus('tailorStatus', 'No active tab found.', 'error'); return; }
  showStatus('tailorStatus', 'Opening sidebar on current page…', 'success');
  chrome.tabs.sendMessage(tab.id, { action: 'tailorCurrentPage' }, (resp) => {
    if (chrome.runtime.lastError || !resp?.ok) {
      showStatus('tailorStatus', 'Could not reach the page. Reload it and try again.', 'error');
    } else {
      window.close();
    }
  });
});

// Dashboard link — open the local server dashboard
document.getElementById('open-dashboard').addEventListener('click', async (e) => {
  e.preventDefault();
  const { serverUrl } = await chrome.storage.local.get(['serverUrl']);
  const url = (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');
  chrome.tabs.create({ url });
});

// Stats — clear
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

function showStatus(elId, msg, type) {
  const el = document.getElementById(elId);
  el.innerHTML = `<div class="status-msg ${type}">${msg}</div>`;
  setTimeout(() => { el.innerHTML = ''; }, 4000);
}

chrome.storage.onChanged.addListener((changes, ns) => {
  if (ns === 'local' && changes.stats) updateStats(changes.stats.newValue);
});

loadSavedData();
