// Content script - runs on all job sites
console.log('AutoApply: Content script loaded');

let sidebarInjected = false;
let currentJobData = null;

// Score the page to detect if it's a job posting
function detectJobPage() {
  const url = window.location.href.toLowerCase();
  const hostname = window.location.hostname.toLowerCase();
  const pageText = document.body.innerText.toLowerCase();
  const pageHTML = document.body.innerHTML.toLowerCase();

  let jobScore = 0;

  const urlPatterns = [
    /job[s]?[-_/]/i, /career[s]?[-_/]/i, /position[s]?[-_/]/i,
    /vacancy/i, /opening[s]?/i, /apply/i, /recruitment/i,
    /hiring/i, /viewjob/i, /job-listing/i, /job-detail/i,
  ];
  urlPatterns.forEach(p => { if (p.test(url)) jobScore += 3; });

  const jobBoardDomains = [
    'indeed.com', 'monster.com', 'dice.com', 'linkedin.com',
    'glassdoor.com', 'ziprecruiter.com', 'careerbuilder.com',
    'simplyhired.com', 'flexjobs.com', 'remote.co',
    'weworkremotely.com', 'remoteok.io', 'remoteok.com', 'remotejobs.com',
    'wellfound.com', 'greenhouse.io', 'lever.co', 'workable.com',
    'smartrecruiters.com', 'bamboohr.com', 'jobvite.com', 'icims.com',
  ];
  jobBoardDomains.forEach(domain => { if (hostname.includes(domain)) jobScore += 10; });

  const contentSignals = {
    'job description': 2, 'about the role': 2, 'responsibilities': 1.5,
    'requirements': 1.5, 'qualifications': 1.5, 'apply now': 2,
    'submit application': 2, 'upload resume': 2, 'what you\'ll do': 1.5,
    'what we\'re looking for': 1.5, 'equal opportunity employer': 1,
  };
  Object.entries(contentSignals).forEach(([phrase, score]) => {
    if (pageText.includes(phrase)) jobScore += score;
  });

  const structurePatterns = [
    /class="[^"]*job[^"]*"/i, /id="[^"]*job[^"]*"/i,
    /class="[^"]*apply[^"]*"/i, /data-job/i,
  ];
  structurePatterns.forEach(p => { if (p.test(pageHTML)) jobScore += 1; });

  document.querySelectorAll('button, a, input[type="submit"]').forEach(el => {
    const text = (el.innerText || '').toLowerCase();
    if (text.includes('apply') || text.includes('submit application')) jobScore += 3;
  });

  console.log('AutoApply: Job detection score =', jobScore);

  if (jobScore >= 8) {
    for (const domain of jobBoardDomains) {
      if (hostname.includes(domain)) return domain.split('.')[0];
    }
    return 'generic';
  }
  return null;
}

function extractJobInfo(site) {
  const jobData = { site, title: '', company: '', location: '', description: '', url: window.location.href, salary: '' };

  try {
    const titleCandidates = [
      document.querySelector('h1'),
      document.querySelector('[class*="title" i][class*="job" i]'),
      document.querySelector('[class*="position" i]'),
      document.querySelector('meta[property="og:title"]'),
    ];
    for (const el of titleCandidates) {
      if (el?.innerText) { jobData.title = el.innerText.trim(); break; }
      if (el?.content)   { jobData.title = el.content.trim(); break; }
    }

    const companyCandidates = [
      document.querySelector('[class*="company" i]'),
      document.querySelector('[class*="employer" i]'),
      document.querySelector('[itemprop="hiringOrganization"]'),
      document.querySelector('meta[property="og:site_name"]'),
    ];
    for (const el of companyCandidates) {
      if (el?.innerText) { jobData.company = el.innerText.trim(); break; }
      if (el?.content)   { jobData.company = el.content.trim(); break; }
    }

    const locationCandidates = [
      document.querySelector('[class*="location" i]'),
      document.querySelector('[data-location]'),
      document.querySelector('[itemprop="jobLocation"]'),
    ];
    for (const el of locationCandidates) {
      if (el?.innerText) { jobData.location = el.innerText.trim(); break; }
    }

    const descCandidates = [
      document.querySelector('[class*="description" i]'),
      document.querySelector('[class*="job-detail" i]'),
      document.querySelector('[id*="description" i]'),
      document.querySelector('article'),
      document.querySelector('main'),
    ];
    for (const el of descCandidates) {
      if (el?.innerText?.length > 200) { jobData.description = el.innerText.trim(); break; }
    }

    if (!jobData.description) {
      let best = { el: null, len: 0 };
      document.querySelectorAll('div, section, article').forEach(el => {
        const len = (el.innerText || '').length;
        if (len > best.len && len > 200) best = { el, len };
      });
      if (best.el) jobData.description = best.el.innerText.trim();
    }

    if (jobData.title.length > 200)   jobData.title   = jobData.title.substring(0, 200);
    if (jobData.company.length > 100) jobData.company = jobData.company.substring(0, 100);
  } catch (err) {
    console.error('AutoApply: Error extracting job info:', err);
  }

  return jobData;
}

function findFormFields() {
  const fields = {
    firstName: null, lastName: null, email: null, phone: null,
    resume: null, coverLetter: null, address: null, city: null,
    state: null, zip: null, linkedin: null, website: null, customFields: [],
  };

  document.querySelectorAll('input, textarea, select').forEach(input => {
    const combined = `${input.id} ${input.name} ${input.placeholder} ${findLabelForInput(input)}`.toLowerCase();
    if (combined.includes('first') && combined.includes('name')) fields.firstName = input;
    else if (combined.includes('last') && combined.includes('name')) fields.lastName = input;
    else if (combined.includes('email')) fields.email = input;
    else if (combined.includes('phone') || combined.includes('mobile')) fields.phone = input;
    else if (combined.includes('resume') || combined.includes('cv')) fields.resume = input;
    else if (combined.includes('cover') && combined.includes('letter')) fields.coverLetter = input;
    else if (combined.includes('address') && !combined.includes('email')) fields.address = input;
    else if (combined.includes('city')) fields.city = input;
    else if (combined.includes('state') || combined.includes('province')) fields.state = input;
    else if (combined.includes('zip') || combined.includes('postal')) fields.zip = input;
    else if (combined.includes('linkedin')) fields.linkedin = input;
    else if (combined.includes('website') || combined.includes('portfolio')) fields.website = input;
    else if (!['hidden','submit','button'].includes(input.type)) {
      fields.customFields.push({ element: input, label: findLabelForInput(input), type: input.type });
    }
  });

  return fields;
}

function findLabelForInput(input) {
  if (input.id) {
    const label = document.querySelector(`label[for="${input.id}"]`);
    if (label) return label.innerText;
  }
  const parent = input.closest('div, fieldset, td');
  if (parent) {
    const label = parent.querySelector('label');
    if (label) return label.innerText;
  }
  return '';
}

function injectFloatingButton() {
  if (document.getElementById('autoapply-fab')) return;
  const fab = document.createElement('div');
  fab.id = 'autoapply-fab';
  fab.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="2" y="7" width="20" height="14" rx="2"></rect>
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
  </svg>`;
  fab.title = 'AutoApply Resume Assistant';
  fab.addEventListener('click', toggleSidebar);
  document.body.appendChild(fab);
}

function toggleSidebar() {
  const existing = document.getElementById('autoapply-sidebar');
  if (existing) { existing.remove(); sidebarInjected = false; }
  else injectSidebar();
}

function injectSidebar() {
  if (sidebarInjected) return;
  const sidebar = document.createElement('div');
  sidebar.id = 'autoapply-sidebar';
  sidebar.innerHTML = `
    <div class="autoapply-header">
      <h3>AutoApply Assistant</h3>
      <button id="autoapply-close">×</button>
    </div>
    <div class="autoapply-content">
      <div id="autoapply-job-info"></div>
      <div id="autoapply-result"></div>
      <div id="autoapply-autofill"></div>
      <div id="autoapply-status"></div>
    </div>`;
  document.body.appendChild(sidebar);
  sidebarInjected = true;
  document.getElementById('autoapply-close').addEventListener('click', toggleSidebar);
  loadJobInfo();
}

async function loadJobInfo() {
  const jobInfoEl = document.getElementById('autoapply-job-info');
  const site = detectJobPage();

  if (!site) {
    jobInfoEl.innerHTML = '<p class="autoapply-error">No job posting detected on this page.</p>';
    return;
  }

  currentJobData = extractJobInfo(site);

  jobInfoEl.innerHTML = `
    <div class="autoapply-card">
      <h4>Job Detected</h4>
      <p><strong>${currentJobData.title || 'Unknown title'}</strong></p>
      <p>${currentJobData.company || ''}</p>
      <p class="autoapply-location">${currentJobData.location || ''}</p>
      <button id="autoapply-optimize-btn" class="autoapply-btn-primary">
        Tailor Resume for This Job
      </button>
    </div>`;

  document.getElementById('autoapply-optimize-btn').addEventListener('click', optimizeResume);
  checkForApplicationForm();
}

function checkForApplicationForm() {
  const autofillEl = document.getElementById('autoapply-autofill');
  const fields = findFormFields();
  const fieldCount = Object.values(fields).filter(f => f && !Array.isArray(f)).length;

  if (fieldCount > 0 || fields.customFields.length > 0) {
    autofillEl.innerHTML = `
      <div class="autoapply-card">
        <h4>Application Form Detected</h4>
        <p>Found ${fieldCount} standard fields</p>
        <button id="autoapply-autofill-btn" class="autoapply-btn-primary">Auto-Fill Form</button>
      </div>`;
    document.getElementById('autoapply-autofill-btn').addEventListener('click', () => autoFillForm(fields));
  }
}

async function optimizeResume() {
  const statusEl = document.getElementById('autoapply-status');
  const resultEl = document.getElementById('autoapply-result');
  statusEl.innerHTML = '<div class="autoapply-loading">Tailoring resume… this takes ~20-30s</div>';

  try {
    const { baseResume } = await chrome.storage.local.get(['baseResume']);

    if (!baseResume) {
      statusEl.innerHTML = `<div class="autoapply-error">
        No resume saved. Open the extension popup → Resume tab and paste your resume text.
      </div>`;
      return;
    }

    const response = await chrome.runtime.sendMessage({
      action: 'optimizeResume',
      jobData: currentJobData,
      baseResume,
    });

    if (response.success) {
      let secretHtml = '';
      if (response.secretInstructions?.length) {
        secretHtml = `<div class="autoapply-secret">
          Secret phrase detected: <strong>${response.secretInstructions.join(', ')}</strong><br>
          Included in cover letter.
        </div>`;
      }

      resultEl.innerHTML = `
        <div class="autoapply-card">
          <h4>Resume Tailored!</h4>
          <div class="autoapply-score">
            <span class="autoapply-score-num">${response.matchScore}%</span> match
          </div>
          <div class="autoapply-keywords">
            ${(response.matchedKeywords || []).map(k => `<span class="autoapply-kw">${k}</span>`).join('')}
          </div>
          ${secretHtml}
          <button id="autoapply-copy-resume" class="autoapply-btn-primary">Copy Resume Text</button>
          ${response.coverLetter ? '<button id="autoapply-copy-cover" class="autoapply-btn-secondary">Copy Cover Letter</button>' : ''}
          ${response.pdfPath ? `<p class="autoapply-pdf-note">PDF saved to your Documents folder</p>` : ''}
        </div>`;

      document.getElementById('autoapply-copy-resume').addEventListener('click', () => {
        navigator.clipboard.writeText(response.optimizedResume)
          .then(() => alert('Resume copied! Paste into Word or Google Docs and save as PDF.'));
      });

      if (response.coverLetter) {
        document.getElementById('autoapply-copy-cover')?.addEventListener('click', () => {
          navigator.clipboard.writeText(response.coverLetter)
            .then(() => alert('Cover letter copied!'));
        });
      }

      statusEl.innerHTML = '<div class="autoapply-success">Ready to apply!</div>';
    } else {
      statusEl.innerHTML = `<div class="autoapply-error">
        ${response.error || 'Optimization failed.'}<br><br>
        Make sure the AutoApply server is running:<br>
        <code>uvicorn app.main:app --reload --port 8000</code>
      </div>`;
    }
  } catch (err) {
    console.error('AutoApply error:', err);
    statusEl.innerHTML = `<div class="autoapply-error">${err.message}</div>`;
  }
}

async function autoFillForm(fields) {
  const statusEl = document.getElementById('autoapply-status');
  statusEl.innerHTML = '<div class="autoapply-loading">Filling form…</div>';

  const { userProfile } = await chrome.storage.local.get(['userProfile']);
  if (!userProfile) {
    statusEl.innerHTML = '<div class="autoapply-error">Set your profile in the extension popup first.</div>';
    return;
  }

  const fill = (el, val) => {
    if (!el || !val) return;
    el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.style.backgroundColor = '#d4edda';
    setTimeout(() => { el.style.backgroundColor = ''; }, 2000);
  };

  fill(fields.firstName, userProfile.firstName);
  fill(fields.lastName, userProfile.lastName);
  fill(fields.email, userProfile.email);
  fill(fields.phone, userProfile.phone);
  fill(fields.address, userProfile.address);
  fill(fields.city, userProfile.city);
  fill(fields.state, userProfile.state);
  fill(fields.zip, userProfile.zip);
  fill(fields.linkedin, userProfile.linkedin);
  fill(fields.website, userProfile.website);

  const filled = Object.values(fields).filter(f => f && !Array.isArray(f) && f.value).length;

  const { stats = {} } = await chrome.storage.local.get(['stats']);
  stats.formsAutofilled = (stats.formsAutofilled || 0) + 1;
  await chrome.storage.local.set({ stats });

  statusEl.innerHTML = `<div class="autoapply-success">Filled ${filled} fields. Review and submit!</div>`;
}

function initialize() {
  const site = detectJobPage();
  if (site) {
    console.log('AutoApply: Job posting detected on', site);
    injectFloatingButton();
    chrome.runtime.sendMessage({ action: 'jobPageDetected', site, url: window.location.href });

    const { stats = {} } = chrome.storage.local.get(['stats']).then(({ stats = {} }) => {
      stats.jobsViewed = (stats.jobsViewed || 0) + 1;
      chrome.storage.local.set({ stats });
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}

// Handle SPA navigation (LinkedIn, etc.)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    const existing = document.getElementById('autoapply-sidebar');
    if (existing) { existing.remove(); sidebarInjected = false; }
    initialize();
  }
}).observe(document, { subtree: true, childList: true });
