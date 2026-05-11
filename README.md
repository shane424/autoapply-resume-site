# Auto Job Applicator - Chrome Extension

A powerful Chrome extension that automates your job search and application process. Find jobs, optimize resumes, and auto-fill applications with AI-powered resume tailoring.

## 🚀 Features

### Core Functionality
- **🔍 Multi-Board Job Search** - Search Indeed, Monster, Dice, and LinkedIn simultaneously
- **🤖 AI Resume Optimization** - Automatically tailor your resume for each specific job
- **⚡ Auto-Fill Applications** - One-click form filling with your profile data
- **📊 Match Scoring** - See how well you match each job (0-100%)
- **📝 Custom Cover Letters** - Generate personalized cover letters for each application
- **💾 Smart Storage** - Saves your profile and optimized resumes
- **📈 Progress Tracking** - Monitor your job search statistics

### On-Page Features
- **Floating Action Button** - Quick access on any job page
- **Smart Job Detection** - Automatically recognizes job postings
- **Form Field Detection** - Identifies and fills common application fields
- **Sidebar Interface** - Clean, non-intrusive UI overlay

## 📦 Installation

### From Source (Development)

1. **Download the Extension**
   ```bash
   # The extension files are in the /home/claude/job-extension directory
   ```

2. **Create Icons** (Optional but recommended)
   - Navigate to `icons/` folder
   - Follow instructions in `icons/README.md` to create PNG icons
   - Or use placeholder images for now

3. **Load in Chrome**
   - Open Chrome and go to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top right)
   - Click "Load unpacked"
   - Select the `job-extension` folder
   - The extension icon will appear in your toolbar!

## 🎯 How to Use

### Initial Setup

1. **Click the Extension Icon** in your Chrome toolbar
2. **Go to Profile Tab**
   - Fill in your contact information
   - This will be used to auto-fill application forms
   - Click "Save Profile"

3. **Go to Resume Tab**
   - Paste your complete master resume
   - Include all experience, skills, education
   - Click "Save Resume"

### Finding Jobs (Two Methods)

#### Method 1: Built-in Search
1. Click extension icon → **Job Search tab**
2. Enter your criteria:
   - Job title (required)
   - Location (optional)
   - Experience level (optional)
   - Keywords (optional)
3. Select job boards to search
4. Click "Search for Jobs"

#### Method 2: Browse Manually
1. Go to Indeed, Monster, Dice, or LinkedIn
2. Search for jobs normally
3. The extension will activate automatically on job pages

### Applying to Jobs

1. **Visit any job posting** on a supported site
2. **Click the floating purple button** (bottom right)
3. The sidebar will open showing:
   - Job information
   - "Optimize Resume" button
   - Auto-fill option (if application form detected)

4. **Click "Optimize Resume for This Job"**
   - Wait ~10 seconds for AI processing
   - See your match score and tailored resume
   - Download optimized resume + cover letter

5. **If application form is present:**
   - Click "Auto-Fill Application"
   - Review the filled information
   - Complete any remaining fields (CAPTCHAs, etc.)
   - Submit your application!

## 🎨 Supported Job Sites

**Works on ANY website with job postings!**

The extension uses smart pattern recognition to detect job postings on any site, including:

### Major Job Boards:
- ✅ **Indeed** (.indeed.com)
- ✅ **Monster** (.monster.com)
- ✅ **Dice** (.dice.com)
- ✅ **LinkedIn** (.linkedin.com) 
- ✅ **Glassdoor** (.glassdoor.com)
- ✅ **ZipRecruiter** (.ziprecruiter.com)
- ✅ **CareerBuilder** (.careerbuilder.com)
- ✅ **SimplyHired** (.simplyhired.com)

### Company Career Pages:
- ✅ **Greenhouse.io** hosted careers
- ✅ **Lever.co** hosted careers
- ✅ **Workable** hosted careers
- ✅ **SmartRecruiters** hosted careers
- ✅ **BambooHR** hosted careers
- ✅ **Any company's** careers page

### Specialized Job Boards:
- ✅ **RemoteOK**, **WeWorkRemotely** (remote jobs)
- ✅ **AngelList/Wellfound** (startups)
- ✅ **FlexJobs** (flexible work)
- ✅ **Tech job boards** (Dice, StackOverflow Jobs, etc.)

### How Detection Works:
The extension analyzes pages for job posting indicators:
- Job-related URLs (/jobs/, /careers/, /apply/)
- Content patterns (requirements, qualifications, apply now)
- HTML structure (job-related classes and IDs)
- Application forms and buttons
- Known job board domains

**If a page has enough job indicators, the extension activates automatically!**

## 📊 Understanding Match Scores

The AI calculates a match score (0-100%) based on:
- **Skills Match** - Your skills vs job requirements
- **Experience Match** - Your experience level vs job level
- **Keyword Alignment** - Resume keywords vs job description
- **Qualification Match** - Education, certifications, etc.

**Score Guide:**
- 80-100%: Excellent match, definitely apply!
- 60-79%: Good match, you meet most requirements
- 40-59%: Moderate match, consider if interested
- 0-39%: Low match, may be a reach

## 🔒 Privacy & Data

- **All data stored locally** in Chrome's storage
- **No data sent to external servers** except Claude API for resume optimization
- **Your resume and profile never leave your browser** except for AI processing
- **Clear your data anytime** from Stats tab

## ⚙️ Technical Details

### Files Structure
```
job-extension/
├── manifest.json          # Extension configuration
├── content.js            # Runs on job sites
├── content.css           # Styling for injected UI
├── background.js         # Handles API calls
├── popup.html           # Extension popup UI
├── popup.js             # Popup functionality
└── icons/               # Extension icons
```

### Permissions Required
- `storage` - Save your profile and resumes locally
- `activeTab` - Interact with job site pages
- `scripting` - Inject content scripts
- Host permissions for supported job sites

### API Usage
- Uses Claude AI API for resume optimization
- API calls made only when you click "Optimize Resume"
- Approximately 4000 tokens per optimization

## 🛠️ Customization

### Adding New Job Sites

Edit `manifest.json` to add new sites to `host_permissions` and `content_scripts.matches`:

```json
{
  "host_permissions": [
    "https://www.newjobsite.com/*"
  ],
  "content_scripts": [{
    "matches": [
      "https://www.newjobsite.com/*"
    ]
  }]
}
```

Then update `content.js` `detectJobPage()` function with the new site's detection logic.

### Customizing Form Fields

Edit the `findFormFields()` function in `content.js` to add new field patterns.

## 🐛 Troubleshooting

### Extension not detecting job pages
- Make sure you're on a supported job site
- Refresh the page after installing the extension
- Check that the URL matches supported patterns

### Auto-fill not working
- Ensure you've saved your profile in the extension popup
- Some sites use non-standard form fields
- Try manually clicking each field first

### Resume optimization failing
- Check your internet connection
- Ensure you've saved your base resume
- Claude API may have rate limits

### Floating button not appearing
- Refresh the page
- Check if the site is in the supported list
- Open browser console for error messages

## 📝 Best Practices

1. **Keep your base resume comprehensive** - Include everything, the AI will tailor it
2. **Review AI-optimized resumes** before submitting - Ensure accuracy
3. **Customize as needed** - The AI optimization is a starting point
4. **Track your applications** - Use the Stats tab to monitor progress
5. **Update your profile regularly** - Keep contact info current

## 🚧 Limitations

- Cannot submit applications automatically (anti-bot protections)
- CAPTCHAs must be solved manually
- Some sites require login to apply
- File upload fields must be handled manually
- Custom questions must be answered manually

## 🔮 Future Enhancements

Potential features for future versions:
- Browser automation for clicking "Apply" buttons
- Integration with more job boards
- Application tracking dashboard
- Email notifications for new matches
- Salary negotiation insights
- Interview scheduling assistance
- Multi-language support

## 📄 License

This extension is provided as-is for personal use. Respect the terms of service of job boards when using this tool.

## 🤝 Support

For issues, questions, or feature requests:
1. Check the Troubleshooting section
2. Review Chrome's extension console for errors
3. Ensure all files are properly loaded

## 💡 Tips for Success

- **Be honest** - Never fabricate experience in your resume
- **Stay organized** - Track which jobs you've applied to
- **Follow up** - The extension helps with applications, but you still need to follow up
- **Network** - Use the extension to save time, then invest that time in networking
- **Quality over quantity** - Apply to jobs that genuinely match your skills

---

**Remember:** This extension automates the tedious parts of job searching, but getting hired still requires a great resume, genuine qualifications, and interview skills. Use it wisely! 🎯
