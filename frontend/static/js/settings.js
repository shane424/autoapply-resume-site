function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function csvToArray(str) {
  return str.split(',').map(s => s.trim()).filter(Boolean);
}

function arrayToCsv(arr) {
  return (arr || []).join(', ');
}

async function loadSettings() {
  const res = await fetch('/api/settings');
  if (!res.ok) return;
  const s = await res.json();

  // LLM provider
  document.querySelectorAll('input[name="llm_provider"]').forEach(r => {
    r.checked = r.value === s.llm?.provider;
  });
  document.getElementById('ollama-model').value = s.llm?.ollama_model || '';
  document.getElementById('ollama-base-url').value = s.llm?.ollama_base_url || '';
  toggleOllamaSettings(s.llm?.provider === 'ollama');

  // Filters
  document.getElementById('filter-keywords').value = arrayToCsv(s.filters?.keywords);
  document.getElementById('filter-roles').value = arrayToCsv(s.filters?.roles);
  document.getElementById('filter-exclude').value = arrayToCsv(s.filters?.exclude_keywords);
  document.getElementById('filter-remote').checked = s.filters?.remote_only ?? true;

  // Apply mode
  document.getElementById('default-mode').value = s.apply?.default_mode || 'semiauto';

  // User profile
  const p = s.user_profile || {};
  document.getElementById('p-first').value = p.first_name || '';
  document.getElementById('p-last').value = p.last_name || '';
  document.getElementById('p-email').value = p.email || '';
  document.getElementById('p-phone').value = p.phone || '';
  document.getElementById('p-linkedin').value = p.linkedin || '';
  document.getElementById('p-website').value = p.website || '';
  document.getElementById('p-cover').value = p.cover_letter_template || '';
}

function toggleOllamaSettings(show) {
  document.getElementById('ollama-settings').style.display = show ? '' : 'none';
}

document.querySelectorAll('input[name="llm_provider"]').forEach(r => {
  r.addEventListener('change', () => toggleOllamaSettings(r.value === 'ollama'));
});

document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById('save-status');
  statusEl.innerHTML = '<span aria-busy="true">Saving…</span>';

  const provider = document.querySelector('input[name="llm_provider"]:checked')?.value || 'claude';
  const payload = {
    llm: {
      provider,
      claude_model: 'claude-3-5-haiku-20241022',
      ollama_model: document.getElementById('ollama-model').value || 'llama3.2',
      ollama_base_url: document.getElementById('ollama-base-url').value || 'http://localhost:11434',
    },
    filters: {
      keywords: csvToArray(document.getElementById('filter-keywords').value),
      roles: csvToArray(document.getElementById('filter-roles').value),
      exclude_keywords: csvToArray(document.getElementById('filter-exclude').value),
      remote_only: document.getElementById('filter-remote').checked,
    },
    apply: {
      default_mode: document.getElementById('default-mode').value,
    },
    user_profile: {
      first_name: document.getElementById('p-first').value,
      last_name: document.getElementById('p-last').value,
      email: document.getElementById('p-email').value,
      phone: document.getElementById('p-phone').value,
      linkedin: document.getElementById('p-linkedin').value,
      website: document.getElementById('p-website').value,
      cover_letter_template: document.getElementById('p-cover').value,
    }
  };

  const res = await fetch('/api/settings', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    statusEl.innerHTML = '<ins>Settings saved.</ins>';
  } else {
    const data = await res.json();
    statusEl.innerHTML = `<span style="color:red">Error: ${escHtml(data.detail)}</span>`;
  }
});

loadSettings();
