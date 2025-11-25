// script.js - OPTIMIZED VERSION
// Handles validation, loading states, error handling, and result display for Islamic Guidance AI

// =============================================================================
// GLOBAL VARIABLES AND INITIALIZATION
// =============================================================================

const queryInput = document.getElementById('query');
const searchBtn = document.getElementById('searchBtn');
const statusDiv = document.getElementById('status');
const toastDiv = document.getElementById('toast');
const resultSection = document.getElementById('result');
const answerDiv = document.getElementById('answer');
const citationsDiv = document.getElementById('citations');

// Apply stored theme on load
const storedTheme = localStorage.getItem('theme') || 'traditional';
document.documentElement.setAttribute('data-theme', storedTheme);

// Listen for theme changes from other tabs/pages
window.addEventListener('storage', (e) => {
    if (e.key === 'theme') {
        document.documentElement.setAttribute('data-theme', e.newValue);
    }
});

// Dark Mode Toggle
const darkModeToggle = document.getElementById('darkModeToggle');
if (darkModeToggle) {
    darkModeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        
        if (currentTheme === 'dark') {
            // Revert to previous theme or default
            const previousTheme = localStorage.getItem('previousTheme') || 'traditional';
            document.documentElement.setAttribute('data-theme', previousTheme);
            localStorage.setItem('theme', previousTheme);
        } else {
            // Save current theme as previous before switching to dark
            localStorage.setItem('previousTheme', currentTheme);
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
        }
    });
}

// =============================================================================
// HADITH COLLECTIONS CONFIGURATION
// =============================================================================

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

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function showToast(message) {
    toastDiv.textContent = message;
    toastDiv.classList.remove('hidden');
    setTimeout(() => {
        toastDiv.classList.add('hidden');
    }, 4000);
}

function setStatus(text) {
    statusDiv.textContent = text;
    statusDiv.classList.remove('hidden');
}

function clearStatus() {
    statusDiv.textContent = '';
    statusDiv.classList.add('hidden');
}

function sanitizeInput(text) {
    if (!text) return '';
    let sanitized = text.replace(/<[^>]*>/g, ''); // Remove HTML tags
    sanitized = sanitized.replace(/[{}]/g, ''); // Remove braces
    return sanitized.trim();
}

function isValidInput(text) {
    return text && text.trim().length >= 10;
}

function truncateJSON(obj, maxLength = 150) {
    if (typeof obj === 'string') {
        return obj.length > maxLength 
            ? obj.substring(0, maxLength) + `... [TRUNCATED ${obj.length - maxLength} chars]` 
            : obj;
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

function formatVectorResults(results) {
    if (!results || results.length === 0) {
        return { 
            answer: "No relevant results found in the vector database.", 
            citations: [] 
        };
    }
    
    let answerText = `**Found ${results.length} relevant results:**\n\n`;
    const citations = [];
    
    results.forEach(r => {
        const emoji = r.source === 'quran' ? '📖' : '📚';
        answerText += `${emoji} **Result #${r.rank}** (Score: ${r.score})\n`;
        answerText += `> ${r.text}\n`;
        answerText += `*Source: ${r.source.toUpperCase()}*\n\n`;
        
        citations.push({
            title: `${r.source.toUpperCase()} (Score: ${r.score})`,
            url: r.url
        });
    });
    
    return { answer: answerText, citations: citations };
}

// =============================================================================
// LOGGING WITH CIRCUIT BREAKER (Issue #8 & #12 - P1/P2)
// =============================================================================

let logFailureCount = 0;
const MAX_LOG_FAILURES = 3;

async function logToServer(level, message) {
    // Circuit breaker: stop trying if we have too many failures
    if (logFailureCount >= MAX_LOG_FAILURES) {
        console.log(`[${level.toUpperCase()}] ${message}`);
        return;
    }
    
    const timestamp = new Date().toISOString();
    console.log(`[${level.toUpperCase()}] ${message}`);
    
    // Non-blocking log request with timeout (Issue #12 - P2)
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000); // 2s timeout
        
        // Don't await - make it non-blocking
        fetch('/api/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level, message, timestamp }),
            signal: controller.signal
        }).then(() => {
            clearTimeout(timeoutId);
            logFailureCount = 0; // Reset on success
        }).catch(e => {
            logFailureCount++;
            if (logFailureCount >= MAX_LOG_FAILURES) {
                console.warn('Disabling server logging due to repeated failures');
            }
        });
        
    } catch (e) {
        logFailureCount++;
        console.error('Failed to send log to server:', e);
    }
}

// =============================================================================
// LOADING STAGES SIMULATION
// =============================================================================

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
    }, 1200);
}

// =============================================================================
// FETCH GUIDANCE FROM API
// =============================================================================

async function fetchGuidance(query) {
    const source = document.getElementById('source').value;
    const hadithCollectionKey = document.getElementById('hadithCollection').value;
    const selectedHadithBooks = HADITH_COLLECTIONS[hadithCollectionKey] || [];
    const hadithCodes = selectedHadithBooks.map(book => book.code);
    
    const isVectorSearch = source === 'external';

    logToServer('info', '='.repeat(80));
    logToServer('info', `[USER ACTION] Starting ${isVectorSearch ? 'Vector Search' : 'Guidance'} request`);
    logToServer('info', `[REQUEST] Query: "${query}"`);
    logToServer('info', `[REQUEST] Source: ${source}`);
    
    try {
        let requestBody;
        let endpoint;

        if (isVectorSearch) {
            endpoint = '/api/vector-search';
            const limit = parseInt(localStorage.getItem('searchLimit') || '3');
            const highQuality = localStorage.getItem('highQualityOnly') === 'true';
            requestBody = {
                query: query,
                source: 'both',
                collections: hadithCodes,
                limit: limit,
                score_threshold: highQuality ? 0.75 : 0.0
            };
        } else {
            endpoint = '/api/guidance';
            requestBody = {
                query,
                source,
                hadith_collection: hadithCodes
            };
        }
        
        logToServer('info', `[API REQUEST] Sending POST to ${endpoint}`);
        logToServer('info', `[API REQUEST] Body: ${JSON.stringify(requestBody)}`);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        logToServer('info', `[API RESPONSE] Status: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            logToServer('error', `[API ERROR] Status ${response.status}`);
            
            // Return structured error for different status codes
            if (response.status === 400) {
                return { error: 'Invalid query', message: errorData.detail || 'Query too short' };
            } else if (response.status === 429) {
                return { error: 'Rate limit', message: 'API quota exceeded. Please try again later.' };
            } else if (response.status === 503) {
                return { error: 'Service unavailable', message: 'Service not available. Please check configuration.' };
            } else if (response.status === 500) {
                return { error: 'Server error', message: errorData.detail || 'Internal server error occurred' };
            }
            
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();
        logToServer('info', '[API RESPONSE] Data parsed successfully');
        
        if (isVectorSearch) {
            return formatVectorResults(data.results);
        }

        // Log truncated response for readability
        const truncatedData = truncateJSON(data, 150);
        logToServer('info', `[API RESPONSE] Data: ${JSON.stringify(truncatedData, null, 2)}`);
        
        return data;
        
    } catch (err) {
        if (err.name === 'AbortError') {
            logToServer('error', '[TIMEOUT] Request timed out after 15s');
            return { error: 'Timeout', message: 'The request took too long. Please try again.' };
        }
        
        logToServer('error', `[NETWORK ERROR] ${err.message}`);
        
        return { 
            error: 'Network error', 
            message: 'Failed to connect to server. Please check if the server is running.' 
        };
    }
}

// =============================================================================
// DISPLAY RESULTS
// =============================================================================

function displayResult(data) {
    logToServer('info', '[DISPLAY] Displaying results to user');
    
    clearStatus();
    resultSection.classList.remove('hidden');
    
    // Check if it's an error
    if (data.error) {
        logToServer('error', `[DISPLAY] Showing error: ${data.error}`);
        answerDiv.innerHTML = `<p class="error-message"><strong>Error:</strong> ${data.message || data.error}</p>`;
        citationsDiv.innerHTML = '';
        return;
    }
    
    logToServer('info', `[DISPLAY] Answer length: ${(data.answer || '').length} characters`);
    
    // Populate answer with basic markdown formatting support
    let answerText = data.answer || '';
    
    // Convert markdown-style formatting to HTML
    // Bold text: **text** -> <strong>text</strong>
    answerText = answerText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Line breaks: \n -> <br>
    answerText = answerText.replace(/\n/g, '<br>');
    
    // Set as HTML to render formatting
    answerDiv.innerHTML = answerText;
    
    // Populate citations if any
    citationsDiv.innerHTML = '';
    if (data.citations && data.citations.length) {
        logToServer('info', `[DISPLAY] Displaying ${data.citations.length} citations`);
        
        // Add a header for citations
        const citationHeader = document.createElement('h3');
        citationHeader.textContent = 'References & Citations';
        citationHeader.style.marginTop = '20px';
        citationHeader.style.marginBottom = '10px';
        citationsDiv.appendChild(citationHeader);
        
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

// =============================================================================
// EVENT LISTENERS
// =============================================================================

searchBtn.addEventListener('click', async () => {
    const query = queryInput.value;
    
    logToServer('info', '[USER ACTION] Search button clicked');
    logToServer('info', `[VALIDATION] Query length: ${query.length} characters`);
    
    if (!isValidInput(query)) {
        logToServer('warning', '[VALIDATION] Query too short, showing toast');
        showToast('Please describe your situation in at least 10 characters.');
        return;
    }
    
    const sanitizedQuery = sanitizeInput(query);
    logToServer('info', '[VALIDATION] Input validated and sanitized');
    
    // Reset previous result
    resultSection.classList.add('hidden');
    answerDiv.textContent = '';
    citationsDiv.innerHTML = '';
    
    // Simulate loading stages then fetch
    simulateLoadingStages(async () => {
        const data = await fetchGuidance(sanitizedQuery);
        
        if (data.error) {
            if (data.error === 'Irrelevant problem') {
                logToServer('warning', '[ERROR] Irrelevant problem detected');
                showToast("This doesn't seem to be a request for guidance. Please try describing a life situation.");
            } else {
                logToServer('error', `[ERROR] Error occurred: ${data.error}`);
                showToast(data.message || 'An error occurred. Please try again later.');
            }
            clearStatus();
            return;
        }
        
        displayResult(data);
    });
});

// Allow Enter key to trigger search
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        searchBtn.click();
    }
});

// =============================================================================
// NEW FEATURES LOGIC
// =============================================================================

// 1. Hadith Selector Logic
const sourceSelect = document.getElementById('source');
const hadithSelect = document.getElementById('hadithCollection');

function updateHadithSelectorState() {
    const source = sourceSelect.value;
    if (source === 'internal') {
        hadithSelect.disabled = true;
        hadithSelect.title = "Hadith selection is disabled for Internal (AI Only) source";
    } else {
        hadithSelect.disabled = false;
        hadithSelect.title = "Select Hadith collection";
    }
}

// Initialize state and add listener
if (sourceSelect && hadithSelect) {
    updateHadithSelectorState();
    sourceSelect.addEventListener('change', updateHadithSelectorState);
}

// 2. Load Example Logic
const loadExampleBtn = document.getElementById('loadExampleBtn');

if (loadExampleBtn) {
    loadExampleBtn.addEventListener('click', async () => {
        try {
            // Add loading state
            const originalText = loadExampleBtn.textContent;
            loadExampleBtn.textContent = 'Loading...';
            loadExampleBtn.disabled = true;
            
            const response = await fetch('/api/example-prompt');
            if (response.ok) {
                const data = await response.json();
                if (data.prompt) {
                    queryInput.value = data.prompt;
                    queryInput.focus();
                    logToServer('info', '[USER ACTION] Loaded example query from backend');
                }
            } else {
                console.error('Failed to fetch example prompt');
                showToast('Failed to load example. Please try again.');
            }
        } catch (err) {
            console.error('Error fetching example:', err);
            showToast('Network error loading example.');
        } finally {
            // Restore button state
            loadExampleBtn.textContent = 'Load Example';
            loadExampleBtn.disabled = false;
        }
    });
}

// 3. Navigation Buttons
// 3. Navigation Buttons
const settingsBtn = document.getElementById('settingsBtn');

function navigateToSettings() {
    window.location.href = 'settings.html';
}

if (settingsBtn) settingsBtn.addEventListener('click', navigateToSettings);

// 4. Credits Modal Logic
const creditsBtn = document.getElementById('creditsBtn');
const creditsModal = document.getElementById('creditsModal');
const closeModal = document.querySelector('.close-modal');

if (creditsBtn && creditsModal) {
    creditsBtn.addEventListener('click', () => {
        creditsModal.classList.remove('hidden');
    });
}

if (closeModal && creditsModal) {
    closeModal.addEventListener('click', () => {
        creditsModal.classList.add('hidden');
    });
}

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === creditsModal) {
        creditsModal.classList.add('hidden');
    }
});
