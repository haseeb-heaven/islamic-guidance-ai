// script.js
// Handles validation, loading states, error handling, and result display for Islamic Guidance AI

const queryInput = document.getElementById('query');
const searchBtn = document.getElementById('searchBtn');
const statusDiv = document.getElementById('status');
const toastDiv = document.getElementById('toast');
const resultSection = document.getElementById('result');
const answerDiv = document.getElementById('answer');
const citationsDiv = document.getElementById('citations');

// Apply stored theme on load - Default to Traditional Islamic
const storedTheme = localStorage.getItem('theme') || 'traditional';
document.documentElement.setAttribute('data-theme', storedTheme);

// Dark Mode Toggle
const darkModeToggle = document.getElementById('darkModeToggle');
if (darkModeToggle) {
  darkModeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  });
}

// Utility to show toast messages
function showToast(message) {
  toastDiv.textContent = message;
  toastDiv.classList.remove('hidden');
  // Auto hide after animation (4s defined in CSS)
  setTimeout(() => {
    toastDiv.classList.add('hidden');
  }, 4000);
}

// Utility to update status text
function setStatus(text) {
  statusDiv.textContent = text;
  statusDiv.classList.remove('hidden');
}

function clearStatus() {
  statusDiv.textContent = '';
  statusDiv.classList.add('hidden');
}

// Hadith Collections Configuration
const HADITH_COLLECTIONS = {
  "Sahihayn": [
    { "name": "Sahih al-Bukhari", "code": "eng-bukhari" },
    { "name": "Sahih Muslim", "code": "eng-muslim" }
  ],
  "Sunan_Arbaah": [
    { "name": "Sunan Abu Dawud", "code": "eng-abudawud" },
    { "name": "Jami At-Tirmidhi", "code": "eng-tirmidhi" },
    { "name": "Sunan an-Nasai", "code": "eng-nasai" },
    { "name": "Sunan Ibn Majah", "code": "eng-ibnmajah" }
  ],
  "Kutub_al_Sittah": [
    { "name": "Sahih al-Bukhari", "code": "eng-bukhari" },
    { "name": "Sahih Muslim", "code": "eng-muslim" },
    { "name": "Sunan Abu Dawud", "code": "eng-abudawud" },
    { "name": "Jami At-Tirmidhi", "code": "eng-tirmidhi" },
    { "name": "Sunan an-Nasai", "code": "eng-nasai" },
    { "name": "Sunan Ibn Majah", "code": "eng-ibnmajah" }
  ],
  "Kutub_as_Sabiah": [
    { "name": "Sahih al-Bukhari", "code": "eng-bukhari" },
    { "name": "Sahih Muslim", "code": "eng-muslim" },
    { "name": "Sunan Abu Dawud", "code": "eng-abudawud" },
    { "name": "Jami At-Tirmidhi", "code": "eng-tirmidhi" },
    { "name": "Sunan an-Nasai", "code": "eng-nasai" },
    { "name": "Sunan Ibn Majah", "code": "eng-ibnmajah" },
    { "name": "Muwatta Malik", "code": "eng-malik" }
  ],
  "Forty_Collections": [
    { "name": "Forty Hadith Qudsi", "code": "eng-qudsi" },
    { "name": "Forty Hadith Nawawi", "code": "eng-nawawi" },
    { "name": "Forty Hadith of Shah Waliullah Dehlawi", "code": "eng-dehlawi" }
  ]
};

// Validate input length
function isValidInput(text) {
  return text && text.trim().length >= 10;
}

// Simulate progressive status updates while awaiting backend response
function simulateLoadingStages(callback) {
  const hadithCollectionKey = document.getElementById('hadithCollection').value;
  const selectedHadithBooks = HADITH_COLLECTIONS[hadithCollectionKey] || [];
  const bookNames = selectedHadithBooks.map(book => book.name).join(', ');
  
  const stages = [
    'Understanding your problem...',
    'Searching Quran...',
    `Consulting Hadith books (${bookNames})...`
  ];
  let index = 0;
  const interval = setInterval(() => {
    setStatus(stages[index]);
    index++;
    if (index === stages.length) {
      clearInterval(interval);
      callback();
    }
  }, 1200); // change stage every 1.2s
}

// Logging utility
async function logToServer(level, message) {
  const timestamp = new Date().toISOString();
  console.log(`[${level.toUpperCase()}] ${message}`); // Keep console log for debugging
  try {
    await fetch('/api/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level, message, timestamp })
    });
  } catch (e) {
    console.error('Failed to send log to server:', e);
  }
}

// Helper to truncate long JSON for logging
function truncateJSON(obj, maxLength = 150) {
  if (typeof obj === 'string') {
    return obj.length > maxLength ? obj.substring(0, maxLength) + `... [TRUNCATED ${obj.length - maxLength} chars]` : obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(item => truncateJSON(item, maxLength));
  }
  if (typeof obj === 'object' && obj !== null) {
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = truncateJSON(value, maxLength);
    }
    return result;
  }
  return obj;
}

async function fetchGuidance(query) {
  const source = document.getElementById('source').value;
  const hadithCollectionKey = document.getElementById('hadithCollection').value;
  const selectedHadithBooks = HADITH_COLLECTIONS[hadithCollectionKey] || [];
  const hadithCodes = selectedHadithBooks.map(book => book.code);
  
  logToServer('info', '='.repeat(80));
  logToServer('info', '[USER ACTION] Starting guidance request');
  logToServer('info', `[REQUEST] Query: "${query}"`);
  logToServer('info', `[REQUEST] Source: ${source}`);
  logToServer('info', `[REQUEST] Hadith Collection: ${hadithCollectionKey}`);
  logToServer('info', `[REQUEST] Hadith Books: ${hadithCodes.join(', ')}`);
  logToServer('info', '='.repeat(80));
  
  try {
    const requestBody = { 
      query, 
      source,
      hadith_collection: hadithCodes
    };
    logToServer('info', `[API REQUEST] Sending POST to /api/guidance`);
    logToServer('info', `[API REQUEST] Body: ${JSON.stringify(requestBody)}`);
    
    const response = await fetch('/api/guidance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    
    logToServer('info', `[API RESPONSE] Status: ${response.status} ${response.statusText}`);
    logToServer('info', `[API RESPONSE] Headers: ${JSON.stringify(Object.fromEntries(response.headers))}`);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      logToServer('error', `[API ERROR] Status ${response.status}`);
      logToServer('error', `[API ERROR] Response: ${JSON.stringify(errorData)}`);
      
      // Return structured error for different status codes
      if (response.status === 400) {
        return { error: 'Invalid query', message: errorData.detail || 'Query too short' };
      } else if (response.status === 429) {
        return { error: 'Rate limit', message: 'API quota exceeded. Please try again later.' };
      } else if (response.status === 503) {
        return { error: 'Service unavailable', message: 'AI model not available. Please check API key in Settings.' };
      } else if (response.status === 500) {
        return { error: 'Server error', message: errorData.detail || 'Internal server error occurred' };
      }
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    logToServer('info', '[API RESPONSE] Data parsed successfully');
    
    // Log truncated response for readability
    const truncatedData = truncateJSON(data, 150);
    logToServer('info', `[API RESPONSE] Data: ${JSON.stringify(truncatedData, null, 2)}`);
    
    // Log citations count if available
    if (data.citations && Array.isArray(data.citations)) {
      logToServer('info', `[API RESPONSE] Citations count: ${data.citations.length}`);
      data.citations.forEach((citation, idx) => {
        logToServer('info', `[CITATION ${idx + 1}] ${citation.title} - ${citation.url}`);
      });
    }
    
    logToServer('info', '[SUCCESS] Returning data to display');
    logToServer('info', '='.repeat(80));
    
    return data;
  } catch (err) {
    logToServer('error', `[NETWORK ERROR] ${err.message}`);
    logToServer('error', `[NETWORK ERROR] Stack: ${err.stack}`);
    logToServer('info', '='.repeat(80));
    return { error: 'Network error', message: 'Failed to connect to server. Please check if the server is running.' };
  }
}

function displayResult(data) {
  logToServer('info', '[DISPLAY] Displaying results to user');
  
  // Hide status
  clearStatus();
  // Show result section
  resultSection.classList.remove('hidden');
  
  // Check if it's an error
  if (data.error) {
    logToServer('error', `[DISPLAY] Showing error: ${data.error}`);
    answerDiv.innerHTML = `<div class="error-message">
      <strong>Error:</strong> ${data.message || data.error}
    </div>`;
    citationsDiv.innerHTML = '';
    return;
  }
  
  logToServer('info', `[DISPLAY] Answer length: ${(data.answer || '').length} characters`);
  
  // Populate answer
  answerDiv.textContent = data.answer || '';
  // Populate citations if any
  citationsDiv.innerHTML = '';
  if (data.citations && data.citations.length) {
    logToServer('info', `[DISPLAY] Displaying ${data.citations.length} citations`);
    const list = document.createElement('ul');
    data.citations.forEach((cite) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = cite.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = cite.title || cite.url;
      li.appendChild(a);
      list.appendChild(li);
    });
    citationsDiv.appendChild(list);
  } else {
    logToServer('info', '[DISPLAY] No citations to display');
  }
  
  logToServer('info', '[DISPLAY] Results displayed successfully');
}

searchBtn.addEventListener('click', async () => {
  const query = queryInput.value;
  
  logToServer('info', '[USER ACTION] Search button clicked');
  logToServer('info', `[VALIDATION] Query length: ${query.length} characters`);
  
  if (!isValidInput(query)) {
    logToServer('warning', '[VALIDATION] Query too short, showing toast');
    showToast('Please describe your situation in at least 10 characters.');
    return;
  }
  
  logToServer('info', '[VALIDATION] Input validated successfully');

  // Reset previous result
  resultSection.classList.add('hidden');
  answerDiv.textContent = '';
  citationsDiv.innerHTML = '';

  // Simulate loading stages then fetch
  simulateLoadingStages(async () => {
    const data = await fetchGuidance(query);
    if (data.error) {
      if (data.error === 'Irrelevant problem') {
        logToServer('warning', '[ERROR] Irrelevant problem detected');
        showToast("This doesn't seem to be a request for guidance. Please try describing a life situation.");
      } else {
        logToServer('error', `[ERROR] Error occurred: ${data.error}`);
        showToast('An error occurred. Please try again later.');
      }
      clearStatus();
      return;
    }
    displayResult(data);
  });
});

// Optional: allow Enter key to trigger search
queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchBtn.click();
  }
});

