// Background service worker
console.log('Auto Job Applicator: Background script loaded');

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'optimizeResume') {
    handleOptimizeResume(request.jobData, request.baseResume, request.userProfile)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async response
  }
  
  if (request.action === 'jobPageDetected') {
    console.log('Job page detected:', request.site, request.url);
    // Could show notification or badge here
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#4F46E5' });
  }
  
  if (request.action === 'searchJobs') {
    handleSearchJobs(request.criteria)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
  
  if (request.action === 'downloadFile') {
    chrome.downloads.download({
      url: request.url,
      filename: request.filename,
      saveAs: request.saveAs || false
    }).then(downloadId => {
      sendResponse({ success: true, downloadId: downloadId });
    }).catch(err => {
      sendResponse({ success: false, error: err.message });
    });
    return true;
  }
});

// Optimize resume using OpenAI ChatGPT API
async function handleOptimizeResume(jobData, baseResume, userProfile) {
  try {
    console.log('Optimizing resume for:', jobData.title, 'at', jobData.company);
    
    // Get API key from storage
    const { openaiApiKey } = await chrome.storage.local.get(['openaiApiKey']);
    
    if (!openaiApiKey) {
      throw new Error('OpenAI API key not found. Please add your OpenAI API key in the extension settings.');
    }
    
    // Build contact info for replacement
    let contactInfoInstructions = '';
    if (userProfile) {
      const contactParts = [];
      if (userProfile.email) contactParts.push(`Email: ${userProfile.email}`);
      if (userProfile.phone) contactParts.push(`Phone: ${userProfile.phone}`);
      if (userProfile.linkedin) contactParts.push(`LinkedIn: ${userProfile.linkedin}`);
      if (userProfile.website) contactParts.push(`GitHub/Portfolio: ${userProfile.website}`);
      
      if (contactParts.length > 0) {
        contactInfoInstructions = `\n\nREAL CONTACT INFO TO USE:
${contactParts.join(' | ')}

IMPORTANT: Replace ANY placeholders like [Your LinkedIn], [Your GitHub], [Your Email], etc. with the actual values above. If a field is not provided above, REMOVE that line entirely from the resume.`;
      }
    }
    
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${openaiApiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o',
        temperature: 0.7,
        max_tokens: 4000,
        messages: [
          {
            role: 'system',
            content: 'You are an expert ATS resume optimizer. You help tailor resumes to match job descriptions while maintaining complete honesty about qualifications. You NEVER leave placeholders in the final output.'
          },
          {
            role: 'user',
            content: `Optimize this resume for the specific job.

JOB TITLE: ${jobData.title}
COMPANY: ${jobData.company}
LOCATION: ${jobData.location}

JOB DESCRIPTION:
${jobData.description}

BASE RESUME:
${baseResume}
${contactInfoInstructions}

CRITICAL RULES:
1. NEVER fabricate experience, skills, or qualifications
2. Reorganize content to emphasize most relevant experience
3. Use keywords from job description where they genuinely apply
4. Quantify achievements where possible
5. Format for ATS compatibility (clear sections, standard headers)
6. Tailor the summary/objective to this specific role
7. NEVER leave placeholders like [Your LinkedIn], [Your Email], etc. - either use the real values provided above or remove those lines
8. If contact info is provided above, use those EXACT values in the contact section
9. Remove any brackets [ ] from the final output

Return ONLY valid JSON (no markdown, no backticks, no explanatory text):
{
  "optimizedResume": "Complete optimized resume text with all sections and NO placeholders",
  "matchScore": 85,
  "matchedKeywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "coverLetter": "Professional cover letter tailored to this role (3-4 paragraphs)",
  "interviewTips": "Key points to emphasize if you get an interview"
}

The matchScore should be 0-100 based on how well the candidate's experience matches requirements.`
          }
        ]
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`API request failed: ${response.status} - ${errorData.error?.message || 'Unknown error'}`);
    }

    const data = await response.json();
    let responseText = data.choices[0].message.content;
    
    console.log('Raw API response:', responseText);
    
    // Clean up response text
    responseText = responseText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    
    let result;
    try {
      result = JSON.parse(responseText);
    } catch (parseError) {
      console.error('Failed to parse JSON:', responseText);
      throw new Error(`AI returned invalid JSON. Try again or check console for details.`);
    }
    
    // Validate the result has required fields
    if (!result.optimizedResume || !result.matchScore) {
      throw new Error('AI response missing required fields. Try again.');
    }
    
    console.log('Resume optimized successfully. Match score:', result.matchScore);
    
    return {
      success: true,
      optimizedResume: result.optimizedResume,
      coverLetter: result.coverLetter || 'Cover letter not generated',
      matchScore: result.matchScore,
      matchedKeywords: result.matchedKeywords || [],
      interviewTips: result.interviewTips || 'No interview tips generated'
    };
    
  } catch (error) {
    console.error('Error optimizing resume:', error);
    throw error;
  }
}

// Search for jobs across multiple platforms
async function handleSearchJobs(criteria) {
  try {
    console.log('Searching for jobs:', criteria);
    
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 3000,
        messages: [
          {
            role: 'user',
            content: `Search for job listings matching these criteria:

Job Title: ${criteria.jobTitle}
Location: ${criteria.location || 'Any'}
Experience Level: ${criteria.experienceLevel || 'Any'}
Keywords: ${criteria.keywords || 'None'}
Job Boards: ${criteria.jobBoards.join(', ')}

Find 10-15 real job postings across the specified job boards. Return ONLY valid JSON (no markdown, no backticks):
[
  {
    "title": "Job Title",
    "company": "Company Name",
    "location": "City, State",
    "url": "https://www.indeed.com/viewjob?jk=...",
    "source": "indeed",
    "postedDate": "2 days ago",
    "salary": "80k-120k" or null,
    "summary": "Brief 1-2 sentence summary"
  }
]

Include real URLs in the correct format for each job board.`
          }
        ]
      })
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }

    const data = await response.json();
    let responseText = data.content[0].text;
    responseText = responseText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    
    const jobs = JSON.parse(responseText);
    
    console.log('Found', jobs.length, 'jobs');
    
    return {
      success: true,
      jobs: jobs
    };
    
  } catch (error) {
    console.error('Error searching jobs:', error);
    throw error;
  }
}

// Clear badge when extension popup is opened
chrome.action.onClicked.addListener(() => {
  chrome.action.setBadgeText({ text: '' });
});
