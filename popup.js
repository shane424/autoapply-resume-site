// Popup JavaScript
console.log('Popup script loaded');

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const tabName = tab.dataset.tab;
    
    // Update active tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    
    // Update active content
    document.querySelectorAll('.tab-content').forEach(content => {
      content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
  });
});

// Load saved data
async function loadSavedData() {
  try {
    const data = await chrome.storage.local.get([
      'openaiApiKey',
      'userProfile',
      'baseResume',
      'stats'
    ]);
    
    // Load API key
    if (data.openaiApiKey) {
      document.getElementById('openaiApiKey').value = data.openaiApiKey;
    }
    
    // Load profile data
    if (data.userProfile) {
      const profile = data.userProfile;
      document.getElementById('firstName').value = profile.firstName || '';
      document.getElementById('lastName').value = profile.lastName || '';
      document.getElementById('email').value = profile.email || '';
      document.getElementById('phone').value = profile.phone || '';
      document.getElementById('address').value = profile.address || '';
      document.getElementById('city').value = profile.city || '';
      document.getElementById('state').value = profile.state || '';
      document.getElementById('zip').value = profile.zip || '';
      document.getElementById('linkedin').value = profile.linkedin || '';
      document.getElementById('website').value = profile.website || '';
    }
    
    // Load resume
    if (data.baseResume) {
      document.getElementById('baseResume').value = data.baseResume;
    }
    
    // Load stats
    if (data.stats) {
      updateStatsDisplay(data.stats);
    }
  } catch (err) {
    console.error('Error loading saved data:', err);
  }
}

// Save API key
document.getElementById('saveApiKey').addEventListener('click', async () => {
  const apiKey = document.getElementById('openaiApiKey').value.trim();
  
  if (!apiKey) {
    showStatus('apiKeyStatus', 'Please enter an API key', 'error');
    return;
  }
  
  if (!apiKey.startsWith('sk-')) {
    showStatus('apiKeyStatus', 'Invalid API key format. OpenAI keys start with "sk-"', 'error');
    return;
  }
  
  try {
    await chrome.storage.local.set({ openaiApiKey: apiKey });
    showStatus('apiKeyStatus', '✅ API key saved successfully! You can now optimize resumes.', 'success');
  } catch (err) {
    console.error('Error saving API key:', err);
    showStatus('apiKeyStatus', 'Failed to save API key', 'error');
  }
});

// Save profile
document.getElementById('saveProfile').addEventListener('click', async () => {
  const profile = {
    firstName: document.getElementById('firstName').value,
    lastName: document.getElementById('lastName').value,
    email: document.getElementById('email').value,
    phone: document.getElementById('phone').value,
    address: document.getElementById('address').value,
    city: document.getElementById('city').value,
    state: document.getElementById('state').value,
    zip: document.getElementById('zip').value,
    linkedin: document.getElementById('linkedin').value,
    website: document.getElementById('website').value
  };
  
  try {
    await chrome.storage.local.set({ userProfile: profile });
    showStatus('profileStatus', 'Profile saved successfully!', 'success');
  } catch (err) {
    console.error('Error saving profile:', err);
    showStatus('profileStatus', 'Failed to save profile', 'error');
  }
});

// Save resume
document.getElementById('saveResume').addEventListener('click', async () => {
  const resume = document.getElementById('baseResume').value;
  
  if (!resume.trim()) {
    showStatus('resumeStatus', 'Please enter your resume', 'error');
    return;
  }
  
  try {
    await chrome.storage.local.set({ baseResume: resume });
    showStatus('resumeStatus', 'Resume saved successfully!', 'success');
  } catch (err) {
    console.error('Error saving resume:', err);
    showStatus('resumeStatus', 'Failed to save resume', 'error');
  }
});

// Start job search
document.getElementById('startJobSearch').addEventListener('click', async () => {
  const jobTitle = document.getElementById('searchJobTitle').value;
  const location = document.getElementById('searchLocation').value;
  const experience = document.getElementById('searchExperience').value;
  const keywords = document.getElementById('searchKeywords').value;
  
  const jobBoards = Array.from(document.querySelectorAll('.job-board:checked'))
    .map(cb => cb.value);
  
  if (!jobTitle.trim()) {
    showStatus('searchStatus', 'Please enter a job title', 'error');
    return;
  }
  
  if (jobBoards.length === 0) {
    showStatus('searchStatus', 'Please select at least one job board', 'error');
    return;
  }
  
  const searchButton = document.getElementById('startJobSearch');
  searchButton.disabled = true;
  searchButton.textContent = 'Searching...';
  
  try {
    const response = await chrome.runtime.sendMessage({
      action: 'searchJobs',
      criteria: {
        jobTitle,
        location,
        experienceLevel: experience,
        keywords,
        jobBoards
      }
    });
    
    if (response.success) {
      showStatus('searchStatus', `Found ${response.jobs.length} jobs! Visit any job page to use auto-fill.`, 'success');
      
      // Could open jobs in new tabs if desired
      // response.jobs.forEach(job => {
      //   chrome.tabs.create({ url: job.url, active: false });
      // });
    } else {
      showStatus('searchStatus', `Error: ${response.error}`, 'error');
    }
  } catch (err) {
    console.error('Error searching jobs:', err);
    showStatus('searchStatus', 'Failed to search for jobs', 'error');
  } finally {
    searchButton.disabled = false;
    searchButton.textContent = '🔍 Search for Jobs';
  }
});

// Clear stats
document.getElementById('clearStats').addEventListener('click', async () => {
  if (confirm('Are you sure you want to clear all statistics?')) {
    const emptyStats = {
      jobsViewed: 0,
      resumesOptimized: 0,
      formsAutofilled: 0,
      totalMatchScore: 0,
      matchScoreCount: 0
    };
    
    await chrome.storage.local.set({ stats: emptyStats });
    updateStatsDisplay(emptyStats);
  }
});

// Update stats display
function updateStatsDisplay(stats) {
  document.getElementById('statsJobsViewed').textContent = stats.jobsViewed || 0;
  document.getElementById('statsResumesOptimized').textContent = stats.resumesOptimized || 0;
  document.getElementById('statsFormsAutofilled').textContent = stats.formsAutofilled || 0;
  
  const avgScore = stats.matchScoreCount > 0 
    ? Math.round(stats.totalMatchScore / stats.matchScoreCount) 
    : 0;
  document.getElementById('statsAvgMatchScore').textContent = avgScore + '%';
}

// Show status message
function showStatus(elementId, message, type) {
  const statusEl = document.getElementById(elementId);
  statusEl.innerHTML = `<div class="status-message ${type}">${message}</div>`;
  
  setTimeout(() => {
    statusEl.innerHTML = '';
  }, 3000);
}

// Initialize on load
loadSavedData();

// Listen for stat updates from content script
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && changes.stats) {
    updateStatsDisplay(changes.stats.newValue);
  }
});
