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

// Respond to popup asking for job data from this tab
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getJobData') {
    const site = detectJobPage();
    const jobData = extractJobInfo(site || 'generic');
    sendResponse({ found: !!site, jobData });
    return true;
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
