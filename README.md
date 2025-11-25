# Islamic Guidance AI

🚀 **Now with AI-Powered Vector Search (RAG)** - Semantically accurate results using Pinecone Vector Database

> [!WARNING]
> **⚠️ This app is BETA. All AI responses must be manually verified. Use links provided to consult authentic sources.**

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/haseeb-heaven/islamic-guidance-ai
   cd islamic-guidance-ai
   ```

2. **Set up environment**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env and add your API keys:
   # - GEMINI_API_KEY: Get from https://aistudio.google.com/api-keys
   # - PINECONE_API_KEY: Get from https://app.pinecone.io/
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Populate Vector Database (Required for Vector Search)**
   ```bash
   # Run the upload script to populate Pinecone with Quran and Hadith data
   python scripts/upload_pinecone.py
   
   # This is a one-time setup step that creates vector embeddings
   # for semantic search capabilities
   ```

5. **Run the application**
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```

6. **Open in browser**
   ```
   http://localhost:8000
   ```

## 🌐 Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=<your-repo-url>)

### Quick Deploy Steps:

1. **Push to GitHub**
   ```bash
   git push origin main
   ```

2. **Import to Vercel**
   - Go to [vercel.com/new](https://vercel.com/new)
   - Import your GitHub repository
   - Vercel auto-detects configuration

3. **Add Environment Variables**
   - In Vercel Dashboard: Settings → Environment Variables
   - Add `GEMINI_API_KEY` with your Gemini API key
   - Add `PINECONE_API_KEY` with your Pinecone API key
   - Select all environments (Production, Preview, Development)
   
   **Note**: Before deploying, ensure you've run `python scripts/upload_pinecone.py` locally to populate your Pinecone vector database with Quran and Hadith data.

4. **Deploy!**
   - Click Deploy button
   - Wait 1-2 minutes
   - Visit your live URL

📖 **Detailed deployment guide**: [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md)

## 📁 Project Structure

```
islamic-guidance-ai/
├── api/                      # Vercel serverless functions
│   └── index.py             # Entry point for backend
├── backend/                  # FastAPI application
│   ├── main.py              # Main API routes
│   ├── services.py          # Quran/Hadith search
│   ├── keyword_extractor.py # Custom keyword extraction
│   ├── cache.py             # Caching logic
│   ├── utils.py             # Utility functions
│   └── fetch_models.py      # Model fetching script
├── frontend/                 # Static web application
│   ├── index.html           # Main page
│   ├── settings.html        # Settings page
│   ├── styles.css           # Styles
│   ├── script.js            # Main logic
│   ├── settings.js          # Settings logic
│   └── public/              # Public assets
├── docs/                     # Documentation
│   └── VERCEL_DEPLOYMENT.md # Deployment guide
├── tests/                    # Test suite
│   ├── backend/             # Backend tests
│   └── frontend/            # Frontend tests
├── screenshots/              # Project screenshots
├── requirements.txt          # Python dependencies
├── vercel.json              # Vercel configuration
└── .env.example             # Environment template
```

## 🎨 UI/UX App Preview

### 🏠 Main Page - Traditional Islamic Theme

![Main Page - Traditional Islamic Theme](screenshots/main_traditional.png)

**Features Highlighted:**
- 🌙 **Dark Mode Toggle** - Fixed position in top-right corner
- 📝 **Large Resizable Textarea** - 6 rows with vertical resize capability
- 🎯 **Full-Width Button** - Prominent "GET GUIDANCE" action button below textarea
- 🔍 **Source Selector** - Choose AI, External Sources, or Both
- 📚 **Hadith Collection Selector** - Select from 5 collection groups
- 🕌 **Traditional Aesthetics** - Warm beige tones with golden borders (#c9a961)
- 🔗 **Settings Link** - Quick access to configuration

---

### ⚙️ Settings Page - Traditional Islamic Theme

![Settings Page - Traditional Islamic Theme](screenshots/settings_traditional.png)

**Settings Features:**
- 🎨 **Theme Dropdown** - Select from 3 beautiful themes (Traditional Islamic, Modern Blue, Minimal White)
- 🔑 **API Key Management** - Securely configure Gemini API key
- 👁️ **Password Toggle** - Show/hide API key visibility
- 💾 **Save Button** - Apply and persist settings
- 🌙 **Dark Mode Toggle** - Consistent across all pages
- ⬅️ **Back to Home** - Easy navigation

---

### 🔍 Query Results - Traditional Islamic Theme

![Query Results - Traditional Islamic Theme](screenshots/query_results_traditional.png)

**Query Results Features:**
- 📖 **Comprehensive Guidance** - AI-powered Islamic advice based on Quran and Hadith
- 🔗 **Direct Citations** - Clickable links to source texts
- 📚 **Source References** - Detailed references to Quran verses and Hadith collections
- ✨ **Clear Formatting** - Easy-to-read guidance with proper formatting
- 🕌 **Traditional Aesthetics** - Consistent with the Traditional Islamic theme

---

### 🌙 Dark Mode - Traditional Islamic Theme

![Dark Mode - Traditional Islamic Theme](screenshots/dark_mode.png)

**Dark Mode Features:**
- 🌑 **One-Click Toggle** - Instant theme switching
- 👀 **Eye Comfort** - Reduces eye strain in low-light
- 🔄 **Persistent** - Remembers your preference
- 🎨 **Works with All Themes** - Compatible with all 3 color schemes
- ⚡ **Smooth Transitions** - Elegant fade animations

**Dark Mode Specs:**
- Background: `#1e1e1e`
- Cards: `rgba(0,0,0,0.6)`
- Text: `#e0e0e0`
- Inputs: `#333` with `#555` borders

---

### ❓ Help & Credits

#### Help Modal
![Help Modal](screenshots/help_modal.png)

#### Credits Modal
![Credits Modal](screenshots/credits_modal.png)

---

### 📱 UI/UX Response

![UI Response](screenshots/external_response.png)

**Response Features:**
- **Rich Formatting**: Clear distinction between AI advice and citations.
- **Source Highlighting**: Quran verses and Hadiths are clearly marked.
- **Interactive Links**: Direct access to source material.

---

### 💡 Load Example Feature

![Load Example](screenshots/load_example.png)

**Ease of Use:**
- **One-Click Examples**: Pre-built prompts for common life situations.
- **Instant Loading**: Populates query and settings instantly.
- **Variety**: Covers mental health, relationships, finance, and more.

---

### ✨ Key UI/UX Features

- **🎨 Multiple Themes**: 3 distinct visual styles to choose from
- **🌙 Dark Mode**: Toggle for comfortable viewing in any lighting
- **📱 Responsive Design**: Adapts seamlessly to all screen sizes
- **♿ Accessibility**: ARIA labels and keyboard navigation
- **🎭 Smooth Animations**: Transitions and hover effects throughout
- **🔗 Direct Citations**: Clickable links to Quran verses and Hadith sources
- **💬 Dynamic Status Messages**: Real-time feedback during searches
- **🎯 Intuitive Layout**: Logical flow from input to results
- **🔍 Clear Typography**: Readable fonts optimized for each theme

## 🔌 API Endpoints

The application provides a RESTful API powered by FastAPI.

### Core Endpoints

#### `POST /api/guidance`
Get AI guidance with Quran/Hadith citations.

**Request Body:**
```json
{
  "query": "How to deal with anxiety?",
  "source": "both",
  "hadith_collection": ["eng-bukhari", "eng-muslim"]
}
```

**Response:**
```json
{
  "answer": "Islam teaches us to turn to Allah...",
  "citations": [
    {
      "title": "Quran 13:28",
      "url": "https://quran.com/13:28"
    }
  ]
}
```

#### `GET /api/quran/search`
Search Quran verses by keyword.
- **URL**: `/api/quran/search?keyword=patience`
- **Response**: JSON array of verses.

#### `GET /api/hadith/search`
Search Hadith collections by topic.
- **URL**: `/api/hadith/search?topic=prayer&collections=eng-bukhari`
- **Response**: JSON array of hadiths.

### Settings & Configuration

#### `POST /api/save-settings`
Save application settings.

**Request Body:**
```json
{
  "apiKey": "AIzaSy...",
  "theme": "traditional",
  "geminiModel": "gemini-2.0-flash-exp"
}
```

#### `POST /api/log`
Receive frontend logs.

**Request Body:**
```json
{
  "level": "INFO",
  "message": "User clicked search button",
  "timestamp": "2025-11-23T12:00:00"
}
```

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Root endpoint returning service info |
| `GET` | `/api/health` | Check API health status and dependencies |
| `POST` | `/api/guidance` | Get AI guidance with Quran/Hadith citations |
| `GET` | `/api/quran/search` | Search Quran verses by keyword |
| `GET` | `/api/hadith/search` | Search Hadith collections by topic |
| `GET` | `/api/get-settings` | Retrieve current application settings |
| `POST` | `/api/log` | Receive frontend logs |
| `GET` | `/api/models` | List available Gemini models |
| `GET` | `/api/models/current` | Get currently selected model |
| `POST` | `/api/models/set` | Set active Gemini model |
| `GET` | `/api/example-prompt` | Get a random example prompt |
| `GET` | `/api/test-keywords` | Test keyword extraction logic |
| `POST` | `/api/admin/clear-cache` | Clear server-side cache |
| `GET` | `/api/admin/run-tests` | Run backend health checks |


## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, Uvicorn
- **AI**: Google Gemini 2.0 Flash
- **Vector Database**: Pinecone (RAG - Retrieval-Augmented Generation)
- **Frontend**: HTML, CSS, Vanilla JavaScript
- **APIs**: Quran.com API, Sunnah.com API
- **Deployment**: Vercel Serverless Functions

### 🔍 Key Features

- **Dynamic Vector Database**: Uses Pinecone and RAG (Retrieval-Augmented Generation) for semantically accurate results, moving beyond simple keyword matching.
- **Intelligent Search**: Vector embeddings enable contextual understanding of queries for more relevant Islamic guidance.
- **Scalable Architecture**: Pinecone's cloud-native vector database ensures fast, reliable searches at any scale.

## 📝 Environment Variables

| Variable           | Description                        | Required |
|--------------------|------------------------------------|----------|
| `GEMINI_API_KEY`   | Google Gemini API key              | Yes      |
| `PINECONE_API_KEY` | Pinecone Vector Database API key   | Yes      |
| `API_KEY`          | Alias for Gemini API key           | No       |
| `THEME`            | Default theme (light/dark)         | No       |
| `GEMINI_MODEL`     | Default Gemini model               | No       |
| `PORT`             | Port number                        | No       |


## 🧪 Testing

### Test API Locally
```bash
# Test guidance endpoint with Hadith collection selection
curl -X POST http://localhost:8000/api/guidance \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I am feeling anxious", 
    "source": "both",
    "hadith_collection": ["eng-bukhari", "eng-muslim"]
  }'

# Test Quran search
curl http://localhost:8000/api/quran/search?keyword=patience

# Test Hadith search
curl http://localhost:8000/api/hadith/search?topic=prayer
```

Once running, visit:
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## ⚠️ Important Notes

### For Production (Vercel)
- ✅ Environment variables must be set in Vercel Dashboard
- ✅ File-based logging is disabled (use Vercel logs)
- ✅ API key saving endpoint is removed for security
- ✅ Static files served by Vercel CDN


## Version
See [CHANGELOG.md](https://github.com/haseeb-heaven/islamic-guidance-ai/blob/develop/CHANGELOG.md) for version history.
Current version: 3.0.0

## 📄 License
[MIT License](https://github.com/haseeb-heaven/islamic-guidance-ai/blob/develop/LICENSE)
Copyright (c) 2025 Haseeb Mir

## � Project Strength and Weakness

### Islamic Guidance AI - Project Rating

Based on comprehensive analysis of the Islamic Guidance AI repository, here's a detailed evaluation across multiple dimensions:

#### 🏗️ Architecture & Design: **8/10**
- **Strengths**: Clean separation of concerns (backend/frontend/api layers), modular services structure, FastAPI implementation with proper lifecycle management.
- **Weaknesses**: Serverless detection logic could be simplified, some circular import handling adds complexity.
- **Note**: Well-architected for both local dev and Vercel deployment with environment-specific optimizations.

#### 🧹 Code Quality: **7/10**
- **Strengths**: Comprehensive error handling, detailed logging with request IDs, proper async/await patterns, type hints via Pydantic models.
- **Weaknesses**: `main.py` is 63KB (too monolithic - should be split), some duplicated validation logic, magic numbers in config (e.g., timeouts, limits).
- **Note**: Good documentation strings but would benefit from breaking into smaller modules.

#### 🔒 Security: **6/10**
- **Strengths**: Rate limiting with Vercel KV storage, CORS properly configured, API key masking in logs, environment-based security controls.
- **Weaknesses**: API key stored in `.env` (acceptable for local dev), no input sanitization for user queries, missing authentication for admin endpoints (`/api/admin/*`).
- **Critical**: `/api/admin/clear-cache` and `/api/admin/run-tests` endpoints are publicly accessible - should require API key or token.
- **Note**: Acceptable for beta but needs hardening before production.

#### ⚡ Performance: **7.5/10**
- **Strengths**: Intelligent caching with TTLs, semaphore-based concurrency limiting (5 concurrent), YAKE keyword extraction (no API calls), GZip compression, module-level model caching.
- **Weaknesses**: 6-second search timeout may be aggressive for slow networks, no CDN integration mentioned, response size validation at 4.5MB is reactive (should prevent earlier).
- **Note**: Good optimization with Issue #1-#22 addressed systematically.

#### 📈 Scalability: **7/10**
- **Strengths**: Serverless-ready architecture, stateless design with external cache, proper async patterns.
- **Weaknesses**: In-memory fallbacks limit horizontal scaling, no database for persistent data, rate limiter depends on Vercel KV availability.
- **Note**: Scales well for read-heavy workloads but lacks write scaling architecture.

#### 🧪 Testing: **5/10**
- **Strengths**: Automated health checks on startup, test endpoint for keyword extraction, structured test directory.
- **Weaknesses**: No visible unit tests in repository, no CI/CD integration mentioned, health checks are basic smoke tests.
- **Note**: Major gap - production code without comprehensive test coverage is risky.

#### 📚 Documentation: **9/10**
- **Strengths**: Excellent README with deployment guides, API endpoint documentation, troubleshooting section, inline code comments with issue tracking.
- **Weaknesses**: Missing architecture diagrams, no API versioning strategy documented.
- **Note**: One of the strongest aspects - clear instructions for both users and developers.

#### 🛡️ Error Handling: **8/10**
- **Strengths**: Graceful degradation patterns, cache failure fallbacks, detailed error logging with context, HTTP exception mapping.
- **Weaknesses**: Generic 500 errors could be more specific, no retry logic for transient external API failures.
- **Note**: Robust error isolation prevents cascade failures.

#### 🎨 User Experience: **8.5/10**
- **Strengths**: Three beautiful themes, responsive design, dark mode, load examples feature, clear citation formatting, real-time status updates.
- **Weaknesses**: No offline mode, limited error messages to users, settings only persist locally.
- **Note**: Polished UI with thoughtful Islamic aesthetics.

#### 🛠️ Maintainability: **7/10**
- **Strengths**: Clear module structure, consistent naming conventions, issue tracking in comments (#1-#23), version tracking in `CHANGELOG.md`.
- **Weaknesses**: Monolithic `main.py` needs refactoring, missing dependency version pinning, no contribution guidelines.
- **Note**: Good foundation but needs cleanup for long-term maintenance.

### 🏆 Overall Project Rating: **8/10**

---

## 🚀 FUTURE Planning to Migrate to NextJS

### Next.js 14 Migration Plan

Convert this project to **Next.js 14 + TypeScript**:

**Stack:** App Router, Tailwind CSS, TanStack Query, Vercel KV, Edge Runtime.

**Requirements:**
- **Exact feature parity** with current FastAPI version.
- **Full TypeScript** (strict mode, no `any`).
- **Three themes + Dark Mode** implementation.
- **Gemini AI** integration with streaming support.
- **Caching Strategy**: 1h for AI responses, 24h for external APIs.
- **Comprehensive error handling & logging**.
- **Modular, optimized, well-commented code**.

## �📜 Credits

- **Hadith API**: [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api)
- **Quran API**: [alquran.cloud](https://alquran.cloud/api)
- **Google Gemini**: [Gemini API Docs](https://ai.google.dev/gemini-api/docs)

## 🙏 Acknowledgments

- Google Gemini AI for providing the AI capabilities
- Quran.com for Quran API
- Sunnah.com for Hadith API

## 📞 Support

For deployment issues, see [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md)

---

**Made with ❤️ for the Muslim community**
