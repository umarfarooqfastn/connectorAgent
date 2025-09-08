# Connector Creator Agent

An autonomous AI agent that creates Fastn.ai connectors by scraping API documentation and automatically generating connector endpoints.

## What It Does

1. **Web Scraping**: Crawls API documentation websites to extract content
2. **AI Endpoint Extraction**: Uses GPT-4.1-mini to find and extract cURL commands from documentation
3. **Autonomous Connector Creation**: Automatically creates connector groups and endpoints in Fastn.ai
4. **Universal Compatibility**: Works with any API documentation format (REST APIs, GraphQL, etc.)

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

3. Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

```bash
python connectorAgent.py <url> <platform_name> [description] [connector_group_id]
```

### Examples

Create new connector group:
```bash
python connectorAgent.py https://docs.openai.com/api OpenAI "OpenAI API integration"
```

Use existing connector group:
```bash
python connectorAgent.py https://api.stripe.com/docs Stripe "Payment processing" existing_group_id
```

## Output

The agent creates:
- **Connector Groups**: With proper authentication configuration
- **Connector Endpoints**: From extracted cURL commands
- **Local Data**: Scraped data and results saved in `scraped_data/` directory
- **Logs**: Execution logs in `connectorAgent.log`

## Features

- Autonomous operation (no manual intervention required)
- Intelligent duplicate detection
- Support for multiple authentication types (OAuth, API Key, Bearer Token, etc.)
- Comprehensive logging and data persistence
- Error handling and retry logic

## Requirements

- Python 3.7+
- OpenAI API key
- Internet connection
- Fastn.ai account (credentials hardcoded for QA environment)