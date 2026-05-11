// ADD THIS FUNCTION to your content.js file (anywhere)
// This creates a PDF using browser's native print-to-PDF

function createPrintableResume(resumeText, filename) {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${filename}</title>
  <style>
    @page { margin: 0.75in; }
    body { font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.4; max-width: 8.5in; margin: 0 auto; padding: 20px; }
    h1 { font-size: 16pt; text-align: center; margin-bottom: 5px; }
    .contact { text-align: center; font-size: 10pt; margin-bottom: 15px; }
    h2 { font-size: 12pt; border-bottom: 1px solid #000; margin-top: 15px; margin-bottom: 5px; }
    p { margin: 5px 0; }
    @media print { body { margin: 0; padding: 0; } }
  </style>
</head>
<body onload="window.print(); setTimeout(() => window.close(), 1000);">
${resumeText.split('\n').map(line => {
  line = line.trim();
  if (!line) return '<br>';
  if (line === line.toUpperCase() && line.length < 50) return `<h2>${line}</h2>`;
  if (line.includes('@') || line.includes('|')) return `<p class="contact">${line}</p>`;
  if (line.startsWith('-')) return `<p>• ${line.substring(1).trim()}</p>`;
  return `<p>${line}</p>`;
}).join('\n')}
</body>
</html>`;
}

// THEN UPDATE YOUR BUTTON CLICK HANDLERS TO:

document.getElementById('download-resume-btn').addEventListener('click', () => {
  let filename = 'shane_smith'; // Change to your name or pull from userProfile
  const printWin = window.open('', '_blank');
  printWin.document.write(createPrintableResume(response.optimizedResume, filename));
  printWin.document.close();
});
