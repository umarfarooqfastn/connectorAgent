# Connector Creator Agent

AI-powered system for creating Fastn.ai connectors with interactive chat interfaces.

## What It Does

1. **Web Scraping**: Crawls API documentation websites to extract content using Selenium WebDriver
2. **AI Endpoint Extraction**: Uses GPT-4.1-mini to find and extract cURL commands from documentation
3. **Connector Creation**: Creates connector groups and endpoints in Fastn.ai with proper authentication
4. **Universal Compatibility**: Works with any API documentation format (REST APIs, GraphQL, etc.)
5. **Interactive Chat**: Conversational interface for step-by-step connector creation with session management

## Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Chrome browser (required for Selenium):
   - **macOS**: `brew install --cask google-chrome`
   - **Ubuntu**: `sudo apt-get install google-chrome-stable`  
   - **Windows**: Download from Google Chrome website

4. Copy the example environment file and configure your credentials:
```bash
cp .env.example .env
```

5. Edit `.env` file with your actual credentials:
```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Fastn Configuration
FASTN_ENV=qa.fastn.ai
FASTN_USERNAME=your_fastn_username
FASTN_PASSWORD=your_fastn_password
FASTN_CLIENT_ID=fastn-app
FASTN_CLIENT_SPACE_ID=your_client_space_id
FASTN_REDIRECT_URI=https://google.com

# Scraping Configuration
MAX_PAGES=10    # Maximum number of pages to scrape (default: 10)
```

## Usage

### Chat Mode (Recommended)
Interactive conversational interface with session management:

```bash
# Start new chat session
python chat_app.py

# List previous chat sessions
python chat_app.py --list

# Resume existing session
python chat_app.py --resume session_20240101_143022
```

### Examples

**Chat mode** - Interactive conversation:
```bash
python chat_app.py
# Then chat: "I want to create a connector for OpenAI API at https://docs.openai.com/api"
```

## Output

The system creates:
- **Connector Groups**: With proper authentication configuration
- **Connector Endpoints**: From extracted cURL commands
- **Local Data**: Scraped data and results saved in `scraped_data/` directory
- **Chat Sessions**: Conversation history saved in `conversations/` directory (chat mode only)
- **Logs**: Execution logs in `app.log`

## Features

### Chat Mode Features 💬
- **🗣️ Natural Conversation** - Chat naturally about what connector you want to create
- **📁 Session Management** - Resume previous conversations anytime
- **🔄 Persistent History** - All conversations saved locally in JSON format
- **🤖 Tool Integration** - AI automatically uses scraping and connector creation tools
- **📝 Session Listing** - View and resume any previous chat session
- **🎯 Context Awareness** - Remembers platform names and connector group IDs across conversation

### Chat Workflow
When using chat mode:

1. **💬 Start Chat** - Natural conversation about your needs
2. **🌐 AI Scrapes** - Agent automatically scrapes documentation when you provide URL
3. **🔍 Review Endpoints** - AI shows what endpoints it found
4. **🏗️ Create Group** - AI suggests auth config and creates connector group
5. **🔧 Build Endpoints** - AI creates each endpoint with proper cURL commands
6. **💾 Save Session** - Everything saved for future reference

### Technical Features
- **Selenium WebDriver** - Handles JavaScript-heavy documentation sites
- **AI-Powered Extraction** - GPT-4.1-mini intelligently finds API endpoints
- **Multiple Auth Types** - OAuth, API Key, Bearer Token, Basic Auth, Custom Input
- **Smart Content Filtering** - Extracts only API-relevant content from docs
- **Error Handling** - Robust error handling with detailed logging
- **Session Persistence** - Resume conversations from exactly where you left off

## Requirements

- Python 3.7+
- OpenAI API key
- Chrome browser (for Selenium WebDriver)
- Internet connection
- Fastn.ai account credentials
- Access to Fastn QA environment (or production with appropriate configuration)