# Quick Installation Guide

## Step 1: Prepare the Extension

The extension is ready in `/home/claude/job-extension/`

**Note about Icons:** The extension will work without icons (Chrome will show a default icon). If you want custom icons:
- Create three PNG files: icon16.png, icon48.png, icon128.png
- Place them in the `icons/` folder
- Use any image editor or online tool
- Recommended colors: Purple gradient (#667eea to #764ba2)

## Step 2: Load in Chrome

1. Open Google Chrome
2. Go to `chrome://extensions/`
3. Toggle "Developer mode" ON (top right corner)
4. Click "Load unpacked"
5. Select the folder: `/home/claude/job-extension/`
6. Done! The extension is now loaded

## Step 3: Initial Setup

1. **Click the extension icon** in your toolbar
2. **Profile Tab:**
   - Enter your contact information
   - Click "Save Profile"
3. **Resume Tab:**
   - Paste your complete resume
   - Click "Save Resume"

## Step 4: Start Using

### Option A: Search for Jobs
- Go to Job Search tab in the extension
- Enter job title and criteria
- Click "Search for Jobs"

### Option B: Browse Job Sites
- Visit Indeed, Monster, Dice, or LinkedIn
- Click on any job posting
- Click the purple floating button (bottom right)
- Click "Optimize Resume for This Job"
- Click "Auto-Fill Application" if form is present

## Features

✅ Detects job postings automatically
✅ Optimizes your resume for each job
✅ Shows match score (0-100%)
✅ Auto-fills application forms
✅ Generates custom cover letters
✅ Downloads complete application packages

## Troubleshooting

**Extension not loading?**
- Make sure all files are in the same folder
- Check that manifest.json is present
- Look for errors in chrome://extensions/

**Floating button not appearing?**
- Refresh the job page after installing
- Make sure you're on a supported site (Indeed, Monster, Dice, LinkedIn)

**Resume optimization not working?**
- Ensure you've saved your base resume
- Check your internet connection
- The AI needs ~10 seconds to process

## Tips

- Keep your master resume comprehensive
- Review AI-generated content before submitting
- Use match scores to prioritize applications
- Track your stats in the Stats tab
- Update your profile regularly

## Support

For issues, check:
1. Chrome extension console (chrome://extensions/ → Details → Inspect views)
2. The README.md file for detailed documentation
3. Browser console on job pages (F12)

---

**You're all set! Start applying to jobs with AI-powered automation!** 🚀
