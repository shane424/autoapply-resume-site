function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadCurrentResume() {
  const res = await fetch('/api/resume/current');
  if (!res.ok) return;
  const data = await res.json();
  if (data) renderResume(data);
}

function renderResume(data) {
  document.getElementById('resume-preview').style.display = '';
  document.getElementById('resume-filename').textContent = data.file_name || 'Resume';

  const contact = data.contact || {};
  document.getElementById('resume-contact').innerHTML =
    Object.entries(contact).map(([k,v]) => `<span><strong>${escHtml(k)}:</strong> ${escHtml(v)}</span>`).join(' &middot; ');

  document.getElementById('resume-summary').textContent = data.summary || '—';

  document.getElementById('resume-skills').innerHTML =
    (data.skills || []).map(s => `<kbd>${escHtml(s)}</kbd>`).join(' ');

  document.getElementById('resume-experience').innerHTML =
    (data.experience || []).map(e => `
      <details>
        <summary><strong>${escHtml(e.title)}</strong> — ${escHtml(e.company)} <small>${escHtml(e.dates)}</small></summary>
        <ul>${(e.bullets||[]).map(b => `<li>${escHtml(b)}</li>`).join('')}</ul>
      </details>
    `).join('');

  document.getElementById('resume-education').innerHTML =
    (data.education || []).map(e => `<p>${escHtml(e.degree)} — ${escHtml(e.school)} (${escHtml(e.year)})</p>`).join('');
}

document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById('upload-status');
  const fileInput = document.getElementById('resume-file');
  if (!fileInput.files.length) return;

  statusEl.innerHTML = '<span aria-busy="true">Uploading and parsing…</span>';
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  const res = await fetch('/api/resume/upload', {method: 'POST', body: formData});
  const data = await res.json();

  if (!res.ok) {
    statusEl.innerHTML = `<span style="color:red">Error: ${escHtml(data.detail)}</span>`;
    return;
  }
  statusEl.innerHTML = '<ins>Resume uploaded successfully!</ins>';
  renderResume(data);
});

document.getElementById('clear-btn').addEventListener('click', async () => {
  await fetch('/api/resume', {method: 'DELETE'});
  document.getElementById('resume-preview').style.display = 'none';
  document.getElementById('upload-status').innerHTML = '<ins>Resume cleared.</ins>';
});

loadCurrentResume();
