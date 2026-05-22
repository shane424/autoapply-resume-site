// Content script - runs on all job sites
console.log('AutoApply: Content script loaded');

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
    'ashbyhq.com', 'rippling.com',
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

    // JSON-LD structured data (reliable on Greenhouse, Ashby, Lever, etc.)
    if (!jobData.company) {
      document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
        if (jobData.company) return;
        try {
          const d = JSON.parse(s.textContent);
          const org = d?.hiringOrganization?.name || d?.author?.name;
          if (org) jobData.company = org;
        } catch {}
      });
    }

    // Page title pattern: "Backend Engineer at Sticker Mule | ..."
    if (!jobData.company) {
      const titleText = document.title || '';
      const m = titleText.match(/\bat\s+([^|–\-]+?)(?:\s*[|–\-]|$)/i);
      if (m) jobData.company = m[1].trim();
    }

    // URL-based fallback for known ATS platforms
    if (!jobData.company) {
      const host = window.location.hostname;
      const path = window.location.pathname.split('/').filter(Boolean);
      if (host.includes('ashbyhq.com') && path[0])          jobData.company = path[0];
      else if (host.includes('greenhouse.io') && path[0])   jobData.company = path[0];
      else if (host.includes('lever.co') && path[0])        jobData.company = path[0];
      else if (host.includes('bamboohr.com'))                jobData.company = host.split('.')[0];
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

// ── Autofill ──────────────────────────────────────────────────────────────────

function _setNativeValue(el, value) {
  // Triggers React/Angular/Vue synthetic change events in addition to native ones
  try {
    const proto = Object.getPrototypeOf(el);
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, value);
    } else {
      el.value = value;
    }
  } catch {
    el.value = value;
  }
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new Event('blur',   { bubbles: true }));
}

function _fillInput(selectors, value) {
  if (!value) return false;
  for (const sel of selectors) {
    try {
      const el = document.querySelector(sel);
      if (el && el.tagName === 'INPUT' && !el.readOnly && !el.disabled) {
        _setNativeValue(el, value);
        return true;
      }
    } catch {}
  }
  return false;
}

function _fillRadio(labelText, value) {
  // Find radio inputs whose label contains `labelText` and check the one matching `value`
  let filled = false;
  document.querySelectorAll('input[type="radio"]').forEach(radio => {
    const label = document.querySelector(`label[for="${radio.id}"]`);
    const text = (label?.innerText || radio.value || '').toLowerCase();
    if (text.includes(value.toLowerCase())) {
      radio.checked = true;
      radio.dispatchEvent(new Event('change', { bubbles: true }));
      filled = true;
    }
  });
  return filled;
}

function _fillWorkdayDropdown(automationId, desiredText) {
  // Click the Workday custom select widget, then pick the matching option
  const widget = document.querySelector(`[data-automation-id="${automationId}"]`);
  if (!widget) return false;
  widget.click();
  return new Promise(resolve => {
    setTimeout(() => {
      const options = document.querySelectorAll('[data-automation-id="promptOption"], [role="option"]');
      for (const opt of options) {
        if ((opt.innerText || '').toLowerCase().includes(desiredText.toLowerCase())) {
          opt.click();
          resolve(true);
          return;
        }
      }
      // Close without selecting if nothing matched
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      resolve(false);
    }, 400);
  });
}

async function autofillForm(profile) {
  const p = profile.personal;
  const comp = profile.compensation;
  const wa   = profile.work_authorization;
  const vet  = profile.veteran_status;
  const dis  = profile.disability;
  const dem  = profile.demographics;
  const q    = profile.questionnaire_defaults;

  let filled = 0;

  // ── Text inputs ──────────────────────────────────────────────────────────────
  const textFields = [
    // First name
    {
      selectors: [
        'input[data-automation-id="firstName"]',
        'input[name="firstName"]', 'input[name="first_name"]',
        'input[id*="firstName" i]', 'input[id*="first_name" i]',
        'input[aria-label*="first name" i]', 'input[placeholder*="first name" i]',
      ],
      value: p.first_name,
    },
    // Last name
    {
      selectors: [
        'input[data-automation-id="lastName"]',
        'input[name="lastName"]', 'input[name="last_name"]',
        'input[id*="lastName" i]', 'input[id*="last_name" i]',
        'input[aria-label*="last name" i]', 'input[placeholder*="last name" i]',
      ],
      value: p.last_name,
    },
    // Full name (single field)
    {
      selectors: [
        'input[data-automation-id="fullName"]',
        'input[name="fullName"]', 'input[name="full_name"]',
        'input[aria-label*="full name" i]', 'input[placeholder*="full name" i]',
      ],
      value: p.full_name,
    },
    // Email
    {
      selectors: [
        'input[data-automation-id="email"]',
        'input[type="email"]', 'input[name="email"]', 'input[id*="email" i]',
        'input[aria-label*="email" i]', 'input[placeholder*="email" i]',
      ],
      value: p.email,
    },
    // Phone
    {
      selectors: [
        'input[data-automation-id="phone"]',
        'input[type="tel"]', 'input[name="phone"]', 'input[id*="phone" i]',
        'input[aria-label*="phone" i]', 'input[placeholder*="phone" i]',
      ],
      value: p.phone_formatted,
    },
    // Address line 1
    {
      selectors: [
        'input[data-automation-id="addressLine1"]',
        'input[name="address"]', 'input[name="address1"]', 'input[name="addressLine1"]',
        'input[id*="address" i]:not([id*="2" i]):not([id*="city" i])',
        'input[aria-label*="address line 1" i]', 'input[placeholder*="street" i]',
      ],
      value: p.address,
    },
    // City
    {
      selectors: [
        'input[data-automation-id="city"]',
        'input[name="city"]', 'input[id*="city" i]',
        'input[aria-label*="city" i]', 'input[placeholder*="city" i]',
      ],
      value: p.city,
    },
    // State
    {
      selectors: [
        'input[data-automation-id="state"]',
        'input[name="state"]', 'input[id*="state" i]',
        'input[aria-label*="state" i]',
      ],
      value: p.state,
    },
    // ZIP / Postal code
    {
      selectors: [
        'input[data-automation-id="postalCode"]',
        'input[name="zip"]', 'input[name="zipCode"]', 'input[name="postal"]', 'input[name="postalCode"]',
        'input[id*="zip" i]', 'input[id*="postal" i]',
        'input[aria-label*="zip" i]', 'input[aria-label*="postal" i]',
      ],
      value: p.zip,
    },
    // LinkedIn
    {
      selectors: [
        'input[data-automation-id="linkedin"]',
        'input[name="linkedin"]', 'input[id*="linkedin" i]',
        'input[aria-label*="linkedin" i]', 'input[placeholder*="linkedin" i]',
      ],
      value: p.linkedin || '',
    },
    // Desired / expected salary
    {
      selectors: [
        'input[data-automation-id="desiredSalary"]',
        'input[name*="salary" i]', 'input[id*="salary" i]',
        'input[aria-label*="salary" i]', 'input[aria-label*="pay" i]',
        'input[placeholder*="salary" i]', 'input[placeholder*="pay expectation" i]',
      ],
      value: comp.desired_salary,
    },
  ];

  for (const { selectors, value } of textFields) {
    if (_fillInput(selectors, value)) filled++;
  }

  // ── Native <select> dropdowns ────────────────────────────────────────────────
  document.querySelectorAll('select').forEach(sel => {
    const label = (
      document.querySelector(`label[for="${sel.id}"]`)?.innerText ||
      sel.getAttribute('aria-label') || sel.getAttribute('name') || ''
    ).toLowerCase();

    let target = '';
    if (label.includes('state'))                              target = p.state;
    else if (label.includes('country'))                       target = p.country;
    else if (label.includes('veteran'))                       target = vet.veteran_answer;
    else if (label.includes('disability'))                    target = dis.disability_answer;
    else if (label.includes('gender'))                        target = dem.gender;
    else if (label.includes('hispanic') || label.includes('latino')) target = dem.hispanic_answer;
    else if (label.includes('ethnicity') || label.includes('race'))  target = dem.race;
    else if (label.includes('sponsor'))                       target = wa.sponsorship_answer;
    else if (label.includes('authorized') || label.includes('work auth')) target = wa.work_auth_answer;
    else if (label.includes('relocat'))                       target = profile.employment.willing_to_relocate_answer;
    else if (label.includes('education') || label.includes('degree'))    target = q.highest_education;
    if (!target) return;

    for (const opt of sel.options) {
      if (opt.text.toLowerCase().includes(target.toLowerCase())) {
        sel.value = opt.value;
        sel.dispatchEvent(new Event('change', { bubbles: true }));
        filled++;
        break;
      }
    }
  });

  // ── Workday custom dropdowns (data-automation-id) ────────────────────────────
  const wdDropdowns = [
    { id: 'countryDropdown',  text: p.country },
    { id: 'stateDropdown',    text: p.state_full },
    { id: 'genderDropdown',   text: dem.gender },
    { id: 'veteranStatus',    text: vet.veteran_answer },
    { id: 'disability',       text: dis.disability_answer },
  ];
  for (const { id, text } of wdDropdowns) {
    try { await _fillWorkdayDropdown(id, text); } catch {}
  }

  // ── Checkboxes / radios labeled with Yes/No questions ────────────────────────
  const yesNoMap = [
    { keywords: ['authorized', 'work in the u'],  answer: wa.work_auth_answer },
    { keywords: ['require.*sponsor', 'visa sponsor'], answer: wa.sponsorship_answer },
    { keywords: ['relocat'],                       answer: profile.employment.willing_to_relocate_answer },
    { keywords: ['18 years', 'over 18'],           answer: q.over_18_answer },
    { keywords: ['previously.*employed', 'worked here'], answer: q.previously_employed_answer },
    { keywords: ['background check'],              answer: q.background_check_answer },
  ];

  document.querySelectorAll('input[type="radio"]').forEach(radio => {
    const labelEl = document.querySelector(`label[for="${radio.id}"]`);
    const container = radio.closest('fieldset, [role="radiogroup"], div');
    const legendText = (container?.querySelector('legend, [role="group"] > label, .question-text')?.innerText || '').toLowerCase();
    const radioLabel = (labelEl?.innerText || radio.value || '').toLowerCase();

    for (const { keywords, answer } of yesNoMap) {
      const matches = keywords.some(kw => new RegExp(kw, 'i').test(legendText));
      if (matches && radioLabel.includes(answer.toLowerCase())) {
        if (!radio.checked) {
          radio.checked = true;
          radio.dispatchEvent(new Event('change', { bubbles: true }));
          filled++;
        }
        break;
      }
    }
  });

  return filled;
}

// ── Message handler ───────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getJobData') {
    const site = detectJobPage();
    const jobData = extractJobInfo(site || 'generic');
    sendResponse({ found: !!site, jobData });
    return true;
  }

  if (request.action === 'autofill') {
    autofillForm(request.profile).then(filled => {
      sendResponse({ filled });
    });
    return true; // keep channel open for async response
  }
});

function initialize() {
  const site = detectJobPage();
  if (site) {
    chrome.runtime.sendMessage({ action: 'jobPageDetected', site, url: window.location.href });
    chrome.storage.local.get(['stats']).then(({ stats = {} }) => {
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
    initialize();
  }
}).observe(document, { subtree: true, childList: true });
