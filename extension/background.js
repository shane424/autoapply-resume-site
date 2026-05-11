// Background service worker — wires the extension to the local AutoApply backend
console.log('AutoApply: Background script loaded');

const DEFAULT_SERVER = 'http://localhost:8000';

async function getServerUrl() {
  const { serverUrl } = await chrome.storage.local.get(['serverUrl']);
  return (serverUrl || DEFAULT_SERVER).replace(/\/$/, '');
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'optimizeResume') {
    handleOptimizeResume(request.jobData, request.baseResume)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === 'jobPageDetected') {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#4F46E5' });
  }
});

chrome.action.onClicked.addListener(() => {
  chrome.action.setBadgeText({ text: '' });
});

// Send job data + resume text to the local FastAPI backend for tailoring
async function handleOptimizeResume(jobData, baseResume) {
  const server = await getServerUrl();

  if (!baseResume || !baseResume.trim()) {
    throw new Error('No resume saved. Open the extension popup → Resume tab and paste your resume.');
  }

  let response;
  try {
    response = await fetch(`${server}/api/tailor/inline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text: baseResume,
        job_title: jobData.title || '',
        job_company: jobData.company || '',
        job_description: jobData.description || '',
        job_url: jobData.url || '',
      }),
    });
  } catch (netErr) {
    throw new Error(
      `Could not reach the AutoApply backend at ${server}. ` +
      'Make sure the server is running: uvicorn app.main:app --reload --port 8000'
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(`Backend error ${response.status}: ${body.detail || 'Unknown error'}`);
  }

  const data = await response.json();

  // Track stats
  const { stats = {} } = await chrome.storage.local.get(['stats']);
  stats.resumesOptimized = (stats.resumesOptimized || 0) + 1;
  stats.totalMatchScore = (stats.totalMatchScore || 0) + (data.match_score || 0);
  stats.matchScoreCount = (stats.matchScoreCount || 0) + 1;
  await chrome.storage.local.set({ stats });

  return {
    success: true,
    optimizedResume: data.resume_text,
    coverLetter: data.cover_letter || '',
    matchScore: data.match_score || 0,
    matchedKeywords: data.keywords_added || [],
    secretInstructions: data.secret_instructions || [],
    pdfPath: data.pdf_path || '',
  };
}
