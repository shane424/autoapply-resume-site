// Content script - runs on job sites
console.log('Auto Job Applicator: Content script loaded');

let sidebarInjected = false;
let currentJobData = null;

// Detect if we're on a job posting page using smart pattern recognition
function detectJobPage() {
  const url = window.location.href.toLowerCase();
  const hostname = window.location.hostname.toLowerCase();
  const pageText = document.body.innerText.toLowerCase();
  const pageHTML = document.body.innerHTML.toLowerCase();
  
  // Count job-related indicators
  let jobScore = 0;
  
  // URL patterns (high confidence)
  const urlPatterns = [
    /job[s]?[-_/]/i,
    /career[s]?[-_/]/i,
    /position[s]?[-_/]/i,
    /vacancy/i,
    /opening[s]?/i,
    /apply/i,
    /recruitment/i,
    /hiring/i,
    /viewjob/i,
    /job-listing/i,
    /job-detail/i,
    /work-at/i
  ];
  
  urlPatterns.forEach(pattern => {
    if (pattern.test(url)) jobScore += 3;
  });
  
  // Known job board domains (very high confidence)
  const jobBoardDomains = [
    'indeed.com', 'monster.com', 'dice.com', 'linkedin.com', 
    'glassdoor.com', 'ziprecruiter.com', 'careerbuilder.com',
    'simplyhired.com', 'reed.co.uk', 'seek.com.au', 'totaljobs.com',
    'cwjobs.co.uk', 'monster.co.uk', 'flexjobs.com', 'remote.co',
    'weworkremotely.com', 'remoteok.io', 'angel.co', 'wellfound.com',
    'greenhouse.io', 'lever.co', 'workable.com', 'smartrecruiters.com',
    'bamboohr.com', 'jobvite.com', 'icims.com', 'taleo.net'
  ];
  
  jobBoardDomains.forEach(domain => {
    if (hostname.includes(domain)) jobScore += 10;
  });
  
  // Content patterns (medium confidence)
  const contentPatterns = {
    // Job description headers
    'job description': 2,
    'position description': 2,
    'role description': 2,
    'about the role': 2,
    'about the position': 2,
    'about this job': 2,
    
    // Responsibility sections
    'responsibilities': 1.5,
    'key responsibilities': 1.5,
    'duties': 1.5,
    'what you\'ll do': 1.5,
    'you will': 1.5,
    
    // Requirements sections
    'requirements': 1.5,
    'qualifications': 1.5,
    'required skills': 1.5,
    'required qualifications': 1.5,
    'what we\'re looking for': 1.5,
    'ideal candidate': 1.5,
    'must have': 1.5,
    
    // Application related
    'apply now': 2,
    'apply for this position': 2,
    'submit application': 2,
    'how to apply': 2,
    'submit your resume': 2,
    'upload resume': 2,
    
    // Employment details
    'salary': 1,
    'compensation': 1,
    'benefits': 1,
    'job type': 1,
    'employment type': 1,
    'full-time': 0.5,
    'part-time': 0.5,
    'contract': 0.5,
    'remote': 0.5,
    'work from home': 0.5,
    
    // Company info in job context
    'posted by': 1,
    'posted date': 1,
    'date posted': 1,
    'job posted': 1,
    'company overview': 1,
    'about the company': 1,
    'why join us': 1,
    
    // Application process
    'application process': 1.5,
    'equal opportunity employer': 1,
    'eeo statement': 1,
    'background check': 0.5
  };
  
  Object.keys(contentPatterns).forEach(pattern => {
    const regex = new RegExp(pattern, 'gi');
    const matches = (pageText.match(regex) || []).length;
    jobScore += matches * contentPatterns[pattern];
  });
  
  // HTML structure patterns
  const structurePatterns = [
    /class="[^"]*job[^"]*"/i,
    /id="[^"]*job[^"]*"/i,
    /class="[^"]*position[^"]*"/i,
    /class="[^"]*apply[^"]*"/i,
    /data-job/i,
    /data-position/i
  ];
  
  structurePatterns.forEach(pattern => {
    if (pattern.test(pageHTML)) jobScore += 1;
  });
  
  // Look for application buttons/forms (high confidence)
  const applyButtons = document.querySelectorAll('button, a, input[type="submit"]');
  applyButtons.forEach(button => {
    const text = button.innerText.toLowerCase();
    if (text.includes('apply') || text.includes('submit application')) {
      jobScore += 3;
    }
  });
  
  // Look for form fields common in applications
  const formFields = document.querySelectorAll('input, textarea');
  let hasResumeField = false;
  let hasCoverLetterField = false;
  
  formFields.forEach(field => {
    const combined = `${field.name} ${field.id} ${field.placeholder}`.toLowerCase();
    if (combined.includes('resume') || combined.includes('cv')) {
      hasResumeField = true;
      jobScore += 2;
    }
    if (combined.includes('cover') && combined.includes('letter')) {
      hasCoverLetterField = true;
      jobScore += 2;
    }
  });
  
  // Threshold for considering this a job page
  // Scores typically range from 0 (definitely not) to 30+ (definitely yes)
  console.log('Auto Job Applicator: Job detection score =', jobScore);
  
  if (jobScore >= 8) {
    // Try to identify the specific job board
    for (const domain of jobBoardDomains) {
      if (hostname.includes(domain)) {
        return domain.split('.')[0]; // Return 'indeed', 'monster', etc.
      }
    }
    return 'generic'; // Generic job posting
  }
  
  return null;
}

// Extract job information using smart content analysis
function extractJobInfo(site) {
  const jobData = {
    site: site,
    title: '',
    company: '',
    location: '',
    description: '',
    url: window.location.href,
    salary: ''
  };
  
  try {
    // Try to find job title
    // Priority: h1 tags, then large headings, then meta tags
    const titleCandidates = [
      document.querySelector('h1'),
      document.querySelector('[class*="title" i][class*="job" i]'),
      document.querySelector('[class*="position" i]'),
      document.querySelector('[data-job-title]'),
      document.querySelector('meta[property="og:title"]'),
      document.querySelector('title')
    ];
    
    for (const candidate of titleCandidates) {
      if (candidate && candidate.innerText) {
        jobData.title = candidate.innerText.trim();
        break;
      } else if (candidate && candidate.content) {
        jobData.title = candidate.content.trim();
        break;
      }
    }
    
    // Try to find company name
    const companyCandidates = [
      document.querySelector('[class*="company" i]'),
      document.querySelector('[class*="employer" i]'),
      document.querySelector('[data-company]'),
      document.querySelector('[itemprop="hiringOrganization"]'),
      document.querySelector('meta[property="og:site_name"]')
    ];
    
    for (const candidate of companyCandidates) {
      if (candidate && candidate.innerText) {
        jobData.company = candidate.innerText.trim();
        break;
      } else if (candidate && candidate.content) {
        jobData.company = candidate.content.trim();
        break;
      }
    }
    
    // Try to find location
    const locationCandidates = [
      document.querySelector('[class*="location" i]'),
      document.querySelector('[class*="city" i]'),
      document.querySelector('[data-location]'),
      document.querySelector('[itemprop="jobLocation"]')
    ];
    
    for (const candidate of locationCandidates) {
      if (candidate && candidate.innerText) {
        jobData.location = candidate.innerText.trim();
        break;
      }
    }
    
    // Try to find salary
    const salaryCandidates = [
      document.querySelector('[class*="salary" i]'),
      document.querySelector('[class*="compensation" i]'),
      document.querySelector('[class*="pay" i]')
    ];
    
    for (const candidate of salaryCandidates) {
      if (candidate && candidate.innerText) {
        jobData.salary = candidate.innerText.trim();
        break;
      }
    }
    
    // Extract job description
    // Look for description containers
    const descriptionCandidates = [
      document.querySelector('[class*="description" i]'),
      document.querySelector('[class*="job-detail" i]'),
      document.querySelector('[id*="description" i]'),
      document.querySelector('[class*="content" i]'),
      document.querySelector('article'),
      document.querySelector('main')
    ];
    
    for (const candidate of descriptionCandidates) {
      if (candidate && candidate.innerText && candidate.innerText.length > 200) {
        jobData.description = candidate.innerText.trim();
        break;
      }
    }
    
    // Fallback: if no description found, get largest text block
    if (!jobData.description) {
      const textBlocks = document.querySelectorAll('div, section, article');
      let largestBlock = { element: null, length: 0 };
      
      textBlocks.forEach(block => {
        const text = block.innerText || '';
        if (text.length > largestBlock.length && text.length > 200) {
          largestBlock = { element: block, length: text.length };
        }
      });
      
      if (largestBlock.element) {
        jobData.description = largestBlock.element.innerText.trim();
      }
    }
    
    // Clean up extracted data
    if (jobData.title.length > 200) {
      jobData.title = jobData.title.substring(0, 200);
    }
    if (jobData.company.length > 100) {
      jobData.company = jobData.company.substring(0, 100);
    }
    if (jobData.location.length > 100) {
      jobData.location = jobData.location.substring(0, 100);
    }
    
  } catch (err) {
    console.error('Error extracting job info:', err);
  }
  
  return jobData;
}

// Find and identify form fields
function findFormFields() {
  const fields = {
    firstName: null,
    lastName: null,
    email: null,
    phone: null,
    resume: null,
    coverLetter: null,
    address: null,
    city: null,
    state: null,
    zip: null,
    linkedin: null,
    website: null,
    customFields: []
  };
  
  // Find all input fields
  const inputs = document.querySelectorAll('input, textarea, select');
  
  inputs.forEach(input => {
    const id = (input.id || '').toLowerCase();
    const name = (input.name || '').toLowerCase();
    const placeholder = (input.placeholder || '').toLowerCase();
    const label = findLabelForInput(input);
    const combined = `${id} ${name} ${placeholder} ${label}`.toLowerCase();
    
    // Match common field patterns
    if (combined.includes('first') && combined.includes('name')) {
      fields.firstName = input;
    } else if (combined.includes('last') && combined.includes('name')) {
      fields.lastName = input;
    } else if (combined.includes('email')) {
      fields.email = input;
    } else if (combined.includes('phone') || combined.includes('mobile')) {
      fields.phone = input;
    } else if (combined.includes('resume') || combined.includes('cv')) {
      fields.resume = input;
    } else if (combined.includes('cover') && combined.includes('letter')) {
      fields.coverLetter = input;
    } else if (combined.includes('address') && !combined.includes('email')) {
      fields.address = input;
    } else if (combined.includes('city')) {
      fields.city = input;
    } else if (combined.includes('state') || combined.includes('province')) {
      fields.state = input;
    } else if (combined.includes('zip') || combined.includes('postal')) {
      fields.zip = input;
    } else if (combined.includes('linkedin')) {
      fields.linkedin = input;
    } else if (combined.includes('website') || combined.includes('portfolio')) {
      fields.website = input;
    } else if (input.type !== 'hidden' && input.type !== 'submit' && input.type !== 'button') {
      // Collect other fields as custom fields
      fields.customFields.push({
        element: input,
        label: label,
        type: input.type,
        name: input.name,
        id: input.id
      });
    }
  });
  
  return fields;
}

function findLabelForInput(input) {
  // Try to find associated label
  if (input.id) {
    const label = document.querySelector(`label[for="${input.id}"]`);
    if (label) return label.innerText;
  }
  
  // Check parent for label
  const parent = input.closest('div, fieldset, td');
  if (parent) {
    const label = parent.querySelector('label');
    if (label) return label.innerText;
  }
  
  return '';
}

// Inject floating action button
function injectFloatingButton() {
  if (document.getElementById('auto-job-fab')) return;
  
  const fab = document.createElement('div');
  fab.id = 'auto-job-fab';
  fab.innerHTML = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
    </svg>
  `;
  fab.title = 'Auto Job Applicator';
  
  fab.addEventListener('click', () => {
    toggleSidebar();
  });
  
  document.body.appendChild(fab);
}

// Toggle sidebar
function toggleSidebar() {
  const sidebar = document.getElementById('auto-job-sidebar');
  
  if (sidebar) {
    sidebar.remove();
    sidebarInjected = false;
  } else {
    injectSidebar();
  }
}

// Inject sidebar
function injectSidebar() {
  if (sidebarInjected) return;
  
  const sidebar = document.createElement('div');
  sidebar.id = 'auto-job-sidebar';
  sidebar.innerHTML = `
    <div class="auto-job-sidebar-header">
      <h3>Auto Job Applicator</h3>
      <button id="close-sidebar">×</button>
    </div>
    <div class="auto-job-sidebar-content">
      <div id="job-info-section"></div>
      <div id="resume-section"></div>
      <div id="autofill-section"></div>
      <div id="status-section"></div>
    </div>
  `;
  
  document.body.appendChild(sidebar);
  sidebarInjected = true;
  
  // Add close button handler
  document.getElementById('close-sidebar').addEventListener('click', toggleSidebar);
  
  // Load and display job info
  loadJobInfo();
}

// Load and display job information
async function loadJobInfo() {
  const jobInfoSection = document.getElementById('job-info-section');
  const site = detectJobPage();
  
  if (!site) {
    jobInfoSection.innerHTML = '<p class="error">No job posting detected on this page. The extension looks for job listings on any website!</p>';
    return;
  }
  
  currentJobData = extractJobInfo(site);
  
  jobInfoSection.innerHTML = `
    <div class="job-info-card">
      <h4>📋 Job Detected</h4>
      <p><strong>${currentJobData.title}</strong></p>
      <p>${currentJobData.company}</p>
      <p class="location">${currentJobData.location}</p>
      <button id="optimize-resume-btn" class="primary-btn">
        🚀 Optimize Resume for This Job
      </button>
    </div>
  `;
  
  document.getElementById('optimize-resume-btn').addEventListener('click', optimizeResume);
  
  // Check for form fields
  checkForApplicationForm();
}

// Check if there's an application form on the page
function checkForApplicationForm() {
  const autofillSection = document.getElementById('autofill-section');
  const fields = findFormFields();
  
  const hasForm = Object.values(fields).some(f => f !== null && !Array.isArray(f)) || 
                  fields.customFields.length > 0;
  
  if (hasForm) {
    autofillSection.innerHTML = `
      <div class="autofill-card">
        <h4>📝 Application Form Detected</h4>
        <p>Found ${Object.values(fields).filter(f => f && !Array.isArray(f)).length} standard fields</p>
        <button id="autofill-btn" class="primary-btn">
          ⚡ Auto-Fill Application
        </button>
      </div>
    `;
    
    document.getElementById('autofill-btn').addEventListener('click', () => autoFillForm(fields));
  }
}

// Optimize resume for the current job
async function optimizeResume() {
  const statusSection = document.getElementById('status-section');
  statusSection.innerHTML = '<div class="loading">Optimizing resume... ⏳</div>';
  
  try {
    // Get base resume and API key from storage
    const { baseResume, userProfile, openaiApiKey } = await chrome.storage.local.get(['baseResume', 'userProfile', 'openaiApiKey']);
    
    if (!openaiApiKey) {
      statusSection.innerHTML = '<div class="error">❌ OpenAI API key not found!<br><br>Please add your API key:<br>1. Click extension icon in toolbar<br>2. Go to Setup tab<br>3. Add your OpenAI API key<br>4. Click Save</div>';
      return;
    }
    
    if (!baseResume) {
      statusSection.innerHTML = '<div class="error">❌ Base resume not found!<br><br>Please add your resume:<br>1. Click extension icon<br>2. Go to Resume tab<br>3. Paste your resume<br>4. Click Save</div>';
      return;
    }
    
    console.log('Sending optimization request...');
    
    // Prepare contact info replacements
    let contactInfo = '';
    if (userProfile) {
      const parts = [];
      if (userProfile.email) parts.push(`Email: ${userProfile.email}`);
      if (userProfile.phone) parts.push(`Phone: ${userProfile.phone}`);
      if (userProfile.linkedin) parts.push(`LinkedIn: ${userProfile.linkedin}`);
      if (userProfile.website) parts.push(`GitHub/Portfolio: ${userProfile.website}`);
      if (parts.length > 0) {
        contactInfo = '\n\nUSER CONTACT INFO (use these actual values, not placeholders):\n' + parts.join(' | ');
      }
    }
    
    // Send message to background script to optimize resume
    const response = await chrome.runtime.sendMessage({
      action: 'optimizeResume',
      jobData: currentJobData,
      baseResume: baseResume,
      userProfile: userProfile
    });
    
    console.log('Response received:', response);
    
    if (response.success) {
      const resumeSection = document.getElementById('resume-section');
      resumeSection.innerHTML = `
        <div class="resume-card">
          <h4>✅ Resume Optimized!</h4>
          <div class="match-score">
            <div class="score-circle" style="--score: ${response.matchScore}">
              ${response.matchScore}%
            </div>
            <span>Match Score</span>
          </div>
          <div class="matched-keywords">
            <strong>Key Matches:</strong>
            ${response.matchedKeywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
          </div>
          <button id="download-resume-btn" class="primary-btn">
            📋 Copy Resume to Clipboard
          </button>
          <button id="download-package-btn" class="secondary-btn">
            📁 View All Saved Resumes
          </button>
        </div>
      `;
      
      // Store optimized content with job details
      const savedResume = {
        company: currentJobData.company,
        title: currentJobData.title,
        date: new Date().toISOString(),
        resume: response.optimizedResume,
        coverLetter: response.coverLetter,
        matchScore: response.matchScore,
        url: currentJobData.url
      };
      
      // Get existing saved resumes
      const { savedResumes = [] } = await chrome.storage.local.get(['savedResumes']);
      
      // Add new resume to front of array
      savedResumes.unshift(savedResume);
      
      // Keep only last 50 resumes
      if (savedResumes.length > 50) {
        savedResumes.pop();
      }
      
      // Save back to storage
      await chrome.storage.local.set({ savedResumes });
      
      console.log('Resume saved! Total saved:', savedResumes.length);
      
      document.getElementById('download-resume-btn').addEventListener('click', () => {
        // Copy to clipboard
        navigator.clipboard.writeText(response.optimizedResume).then(() => {
          alert('✅ Resume copied to clipboard!\n\nPaste into Word/Google Docs and save as PDF');
        });
      });
      
      document.getElementById('download-package-btn').addEventListener('click', async () => {
        // Show all saved resumes
        const { savedResumes = [] } = await chrome.storage.local.get(['savedResumes']);
        
        if (savedResumes.length === 0) {
          alert('No saved resumes yet. Optimize a resume first!');
          return;
        }
        
        // Create modal/list of saved resumes
        showSavedResumesList(savedResumes);
      });
      
      statusSection.innerHTML = '<div class="success">✅ Ready to apply!</div>';
    } else {
      console.error('Optimization failed:', response.error);
      
      // Parse common errors and provide helpful messages
      let errorMessage = response.error || 'Unknown error';
      let helpText = '';
      
      if (errorMessage.includes('API key')) {
        helpText = 'Check that your OpenAI API key is correct in the Setup tab.';
      } else if (errorMessage.includes('quota') || errorMessage.includes('insufficient')) {
        helpText = 'Add credits to your OpenAI account: platform.openai.com/account/billing';
      } else if (errorMessage.includes('rate limit')) {
        helpText = 'Wait 1 minute and try again (too many requests).';
      } else if (errorMessage.includes('401')) {
        helpText = 'Invalid API key. Get a new one from platform.openai.com/api-keys';
      } else if (errorMessage.includes('429')) {
        helpText = 'Rate limit or out of credits. Check platform.openai.com/usage';
      } else {
        helpText = 'Check console (F12) for details. Verify API key and internet connection.';
      }
      
      statusSection.innerHTML = `<div class="error">❌ Optimization failed<br><br><strong>Error:</strong> ${errorMessage}<br><br><strong>Fix:</strong> ${helpText}</div>`;
    }
  } catch (err) {
    console.error('Error optimizing resume:', err);
    statusSection.innerHTML = `<div class="error">❌ Failed to optimize resume<br><br><strong>Error:</strong> ${err.message}<br><br><strong>Check:</strong><br>• Extension is loaded correctly<br>• API key is saved<br>• Internet connection works<br>• Console (F12) for details</div>`;
  }
}

// Auto-fill form with user data
async function autoFillForm(fields) {
  const statusSection = document.getElementById('status-section');
  statusSection.innerHTML = '<div class="loading">Auto-filling form... ⏳</div>';
  
  try {
    const { userProfile } = await chrome.storage.local.get(['userProfile']);
    
    if (!userProfile) {
      statusSection.innerHTML = '<div class="error">❌ Please set your profile in the extension popup first!</div>';
      return;
    }
    
    let filledCount = 0;
    
    // Fill standard fields
    if (fields.firstName && userProfile.firstName) {
      fields.firstName.value = userProfile.firstName;
      fields.firstName.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.lastName && userProfile.lastName) {
      fields.lastName.value = userProfile.lastName;
      fields.lastName.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.email && userProfile.email) {
      fields.email.value = userProfile.email;
      fields.email.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.phone && userProfile.phone) {
      fields.phone.value = userProfile.phone;
      fields.phone.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.address && userProfile.address) {
      fields.address.value = userProfile.address;
      fields.address.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.city && userProfile.city) {
      fields.city.value = userProfile.city;
      fields.city.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.state && userProfile.state) {
      fields.state.value = userProfile.state;
      fields.state.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.zip && userProfile.zip) {
      fields.zip.value = userProfile.zip;
      fields.zip.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.linkedin && userProfile.linkedin) {
      fields.linkedin.value = userProfile.linkedin;
      fields.linkedin.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    if (fields.website && userProfile.website) {
      fields.website.value = userProfile.website;
      fields.website.dispatchEvent(new Event('input', { bubbles: true }));
      filledCount++;
    }
    
    statusSection.innerHTML = `<div class="success">✅ Auto-filled ${filledCount} fields! Review and submit when ready.</div>`;
    
    // Highlight filled fields
    Object.values(fields).forEach(field => {
      if (field && field.value && !Array.isArray(field)) {
        field.style.backgroundColor = '#d4edda';
        setTimeout(() => {
          field.style.backgroundColor = '';
        }, 2000);
      }
    });
    
  } catch (err) {
    console.error('Error auto-filling form:', err);
    statusSection.innerHTML = '<div class="error">❌ Failed to auto-fill form</div>';
  }
}

// Format resume with clean structure
function formatResumeForDownload(resumeText) {
  // Add clear formatting and structure
  let formatted = '═'.repeat(80) + '\n';
  formatted += 'PROFESSIONAL RESUME\n';
  formatted += '═'.repeat(80) + '\n\n';
  formatted += resumeText;
  formatted += '\n\n' + '═'.repeat(80) + '\n';
  formatted += 'Generated by Auto Job Applicator\n';
  formatted += '═'.repeat(80);
  return formatted;
}

// Download file with subfolder support
function downloadFileToFolder(content, filename, folderName) {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  // Include folder in filename - browser will create the subfolder
  a.download = `${folderName}/${filename}`;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  
  // Cleanup
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

// Show list of all saved resumes
function showSavedResumesList(savedResumes) {
  const resumeSection = document.getElementById('resume-section');
  
  let html = '<div style="max-height: 400px; overflow-y: auto;">';
  html += '<h3 style="margin-bottom: 15px;">📁 Your Saved Resumes</h3>';
  
  savedResumes.forEach((resume, index) => {
    const date = new Date(resume.date).toLocaleDateString();
    html += `
      <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; border-radius: 4px; background: #f9f9f9;">
        <div style="font-weight: bold; margin-bottom: 5px;">${resume.company} - ${resume.title}</div>
        <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
          📅 ${date} | Match: ${resume.matchScore}%
        </div>
        <button class="copy-saved-btn" data-index="${index}" style="background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 5px;">
          📋 Copy Resume
        </button>
        <button class="copy-cover-btn" data-index="${index}" style="background: #48bb78; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
          📋 Copy Cover Letter
        </button>
      </div>
    `;
  });
  
  html += '</div>';
  html += '<button id="back-to-current" style="margin-top: 15px; width: 100%; padding: 10px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">← Back to Current Resume</button>';
  
  resumeSection.innerHTML = html;
  
  // Add event listeners
  document.querySelectorAll('.copy-saved-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const index = parseInt(btn.getAttribute('data-index'));
      navigator.clipboard.writeText(savedResumes[index].resume).then(() => {
        alert('✅ Resume copied! Paste into Word and save as PDF.');
      });
    });
  });
  
  document.querySelectorAll('.copy-cover-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const index = parseInt(btn.getAttribute('data-index'));
      navigator.clipboard.writeText(savedResumes[index].coverLetter).then(() => {
        alert('✅ Cover letter copied!');
      });
    });
  });
  
  document.getElementById('back-to-current').addEventListener('click', () => {
    location.reload();
  });
}

// Initialize on page load
function initialize() {
  const site = detectJobPage();
  if (site) {
    console.log('Auto Job Applicator: Job posting detected on', site, '- Extension activated');
    injectFloatingButton();
    
    // Notify user that extension is ready
    chrome.runtime.sendMessage({
      action: 'jobPageDetected',
      site: site,
      url: window.location.href
    });
  } else {
    console.log('Auto Job Applicator: No job posting detected on this page');
  }
}

// Run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}

// Listen for URL changes (for SPAs like LinkedIn)
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    initialize();
  }
}).observe(document, { subtree: true, childList: true });
