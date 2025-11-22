/**
 * Settings Page JavaScript
 * Handles API key configuration and theme settings
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
    API_ENDPOINTS: {
        GET_KEY: '/api/get-api-key',
        SAVE_KEY: '/api/save-api-key',
        HEALTH: '/health'
    },
    STORAGE_KEYS: {
        THEME: 'selectedTheme',
        DARK_MODE: 'darkMode',
        API_KEY: 'geminiApiKey'
    },
    THEMES: {
        TRADITIONAL: 'traditional',
        MODERN: 'modern',
        MINIMAL: 'minimal'
    }
};

// ============================================================================
// DOM ELEMENTS
// ============================================================================

let elements = {};

function initializeElements() {
    elements = {
        apiKeyInput: document.getElementById('api-key'),
        togglePasswordBtn: document.getElementById('toggle-password'),
        themeSelect: document.getElementById('theme-select'),
        saveBtn: document.getElementById('save-btn'),
        statusMessage: document.getElementById('status-message'),
        darkModeToggle: document.getElementById('dark-mode-toggle'),
        loadingIndicator: document.getElementById('loading')
    };
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Show status message to user
 */
function showStatus(message, type = 'info', duration = 5000) {
    console.log(`[STATUS] ${type.toUpperCase()}: ${message}`);
    
    if (elements.statusMessage) {
        elements.statusMessage.textContent = message;
        elements.statusMessage.className = `status-message ${type}`;
        elements.statusMessage.style.display = 'block';
        
        if (duration > 0) {
            setTimeout(() => {
                elements.statusMessage.style.display = 'none';
            }, duration);
        }
    }
}

/**
 * Show/hide loading indicator
 */
function setLoading(isLoading) {
    if (elements.loadingIndicator) {
        elements.loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
    
    if (elements.saveBtn) {
        elements.saveBtn.disabled = isLoading;
        elements.saveBtn.textContent = isLoading ? '⏳ Saving...' : '💾 Save Settings';
    }
}

/**
 * Safe API call with error handling
 */
async function safeApiCall(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    const finalOptions = { ...defaultOptions, ...options };
    
    console.log(`[API] ${finalOptions.method} ${url}`);
    
    try {
        const response = await fetch(url, finalOptions);
        const data = await response.json();
        
        console.log(`[API] Response:`, data);
        
        return {
            ok: response.ok,
            status: response.status,
            data: data
        };
        
    } catch (error) {
        console.error(`[API] Error:`, error);
        return {
            ok: false,
            status: 0,
            data: { error: error.message }
        };
    }
}

// ============================================================================
// API KEY MANAGEMENT
// ============================================================================

/**
 * Load existing API key from server
 */
async function loadApiKey() {
    console.log('[INIT] Loading API key...');
    setLoading(true);
    
    try {
        const result = await safeApiCall(CONFIG.API_ENDPOINTS.GET_KEY);
        
        if (result.ok && result.data.has_key) {
            if (elements.apiKeyInput) {
                elements.apiKeyInput.value = result.data.api_key;
                elements.apiKeyInput.placeholder = 'API key is configured';
            }
            showStatus('✅ API key loaded successfully', 'success', 3000);
        } else if (result.ok && !result.data.has_key) {
            showStatus('ℹ️ No API key configured. Please enter your Gemini API key.', 'info', 5000);
        } else {
            console.warn('[WARN] Could not load API key:', result.data);
            showStatus('⚠️ Could not load API key status', 'warning', 3000);
        }
    } catch (error) {
        console.error('[ERROR] Failed to load API key:', error);
        showStatus('⚠️ Error loading API key', 'warning', 3000);
    } finally {
        setLoading(false);
    }
}

/**
 * Save API key to server
 */
async function saveApiKey(apiKey) {
    if (!apiKey || apiKey.length < 10) {
        showStatus('❌ Please enter a valid API key (minimum 10 characters)', 'error');
        return false;
    }
    
    console.log('[API] Saving API key...');
    setLoading(true);
    
    try {
        const result = await safeApiCall(CONFIG.API_ENDPOINTS.SAVE_KEY, {
            method: 'POST',
            body: JSON.stringify({ api_key: apiKey })
        });
        
        if (result.ok) {
            if (result.data.success) {
                showStatus('✅ API key saved successfully!', 'success');
                
                // Store in localStorage as backup
                localStorage.setItem(CONFIG.STORAGE_KEYS.API_KEY, apiKey);
                
                return true;
            } else {
                // Vercel environment - show instructions
                const message = result.data.message || 'Cannot save API key on Vercel';
                const instructions = result.data.instructions || '';
                
                showStatus(`ℹ️ ${message}\n\n${instructions}`, 'info', 10000);
                
                // Store in localStorage for client-side use
                localStorage.setItem(CONFIG.STORAGE_KEYS.API_KEY, apiKey);
                
                return false;
            }
        } else {
            const errorMsg = result.data.error || result.data.detail || 'Failed to save API key';
            showStatus(`❌ ${errorMsg}`, 'error');
            return false;
        }
        
    } catch (error) {
        console.error('[ERROR] Save API key failed:', error);
        showStatus('❌ Error saving API key. Please try again.', 'error');
        return false;
    } finally {
        setLoading(false);
    }
}

/**
 * Toggle password visibility
 */
function togglePasswordVisibility() {
    if (!elements.apiKeyInput || !elements.togglePasswordBtn) return;
    
    const isPassword = elements.apiKeyInput.type === 'password';
    elements.apiKeyInput.type = isPassword ? 'text' : 'password';
    elements.togglePasswordBtn.textContent = isPassword ? '🙈' : '👁️';
    
    console.log(`[UI] Password visibility: ${isPassword ? 'shown' : 'hidden'}`);
}

// ============================================================================
// THEME MANAGEMENT
// ============================================================================

/**
 * Load saved theme
 */
function loadTheme() {
    const savedTheme = localStorage.getItem(CONFIG.STORAGE_KEYS.THEME) || CONFIG.THEMES.TRADITIONAL;
    
    if (elements.themeSelect) {
        elements.themeSelect.value = savedTheme;
    }
    
    applyTheme(savedTheme);
    console.log(`[THEME] Loaded theme: ${savedTheme}`);
}

/**
 * Apply theme to page
 */
function applyTheme(theme) {
    document.body.className = theme;
    localStorage.setItem(CONFIG.STORAGE_KEYS.THEME, theme);
    console.log(`[THEME] Applied theme: ${theme}`);
}

/**
 * Load dark mode preference
 */
function loadDarkMode() {
    const darkMode = localStorage.getItem(CONFIG.STORAGE_KEYS.DARK_MODE) === 'true';
    
    if (elements.darkModeToggle) {
        elements.darkModeToggle.checked = darkMode;
    }
    
    if (darkMode) {
        document.body.classList.add('dark-mode');
    }
    
    console.log(`[THEME] Dark mode: ${darkMode ? 'enabled' : 'disabled'}`);
}

/**
 * Toggle dark mode
 */
function toggleDarkMode() {
    const isDarkMode = document.body.classList.toggle('dark-mode');
    localStorage.setItem(CONFIG.STORAGE_KEYS.DARK_MODE, isDarkMode);
    console.log(`[THEME] Dark mode toggled: ${isDarkMode}`);
}

// ============================================================================
// SETTINGS SAVE
// ============================================================================

/**
 * Save all settings
 */
async function saveSettings() {
    console.log('[SAVE] Saving all settings...');
    
    // Save theme
    if (elements.themeSelect) {
        const selectedTheme = elements.themeSelect.value;
        applyTheme(selectedTheme);
    }
    
    // Save dark mode
    const darkMode = elements.darkModeToggle ? elements.darkModeToggle.checked : false;
    localStorage.setItem(CONFIG.STORAGE_KEYS.DARK_MODE, darkMode);
    
    // Save API key
    if (elements.apiKeyInput) {
        const apiKey = elements.apiKeyInput.value.trim();
        
        if (apiKey) {
            const saved = await saveApiKey(apiKey);
            
            if (saved) {
                showStatus('✅ All settings saved successfully!', 'success');
            } else {
                showStatus('⚠️ Settings saved locally (API key note above)', 'warning');
            }
        } else {
            showStatus('✅ Theme settings saved successfully!', 'success');
        }
    } else {
        showStatus('✅ Settings saved successfully!', 'success');
    }
    
    console.log('[SAVE] Settings save complete');
}

// ============================================================================
// EVENT LISTENERS
// ============================================================================

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Password toggle
    if (elements.togglePasswordBtn) {
        elements.togglePasswordBtn.addEventListener('click', togglePasswordVisibility);
    }
    
    // Theme change
    if (elements.themeSelect) {
        elements.themeSelect.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });
    }
    
    // Dark mode toggle
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('change', toggleDarkMode);
    }
    
    // Save button
    if (elements.saveBtn) {
        elements.saveBtn.addEventListener('click', saveSettings);
    }
    
    // API key input - clear status on typing
    if (elements.apiKeyInput) {
        elements.apiKeyInput.addEventListener('input', () => {
            if (elements.statusMessage) {
                elements.statusMessage.style.display = 'none';
            }
        });
    }
    
    console.log('[INIT] Event listeners setup complete');
}

// ============================================================================
// INITIALIZATION
// ============================================================================

/**
 * Initialize settings page
 */
async function initializeSettings() {
    console.log('=' . repeat(60));
    console.log('[INIT] Settings Page Initializing...');
    console.log('=' . repeat(60));
    
    try {
        // Initialize DOM elements
        initializeElements();
        
        // Setup event listeners
        setupEventListeners();
        
        // Load saved settings
        loadTheme();
        loadDarkMode();
        
        // Load API key
        await loadApiKey();
        
        console.log('[INIT] ✅ Settings page initialized successfully');
        
    } catch (error) {
        console.error('[INIT] ❌ Initialization error:', error);
        showStatus('⚠️ Error loading settings. Please refresh the page.', 'error', 0);
    }
}

// ============================================================================
// PAGE LOAD
// ============================================================================

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSettings);
} else {
    initializeSettings();
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CONFIG,
        saveApiKey,
        loadApiKey,
        applyTheme,
        toggleDarkMode
    };
}
