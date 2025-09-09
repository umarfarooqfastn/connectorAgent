from openai import OpenAI
import requests
import json
import time
import os
from dotenv import load_dotenv
import urllib.parse
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Use the ORIGINAL system prompt from app.py - NO changes, NO platform-specific examples
ORIGINAL_SYSTEM_PROMPT = """
You are a Connector Creation Assistant for Fastn.ai. Your job is to help users create connectors by following a structured workflow.

Don't Pass empty object while creating connector group make sure you are setting up custom auth (key value based, username password ,bearer or any other) or Oauth with valid json and get confirmation from user as well return json to user.
You need to pass auth configuration correctly other wise it will fail for user.

**CRITICAL AUTH RULES:**
- ALL auth configurations MUST have "type" and "details" structure
- For bearer token type: ALWAYS use "access_token" field name (NOT "bearerToken")
- Configuration must match EXACTLY the examples provided below
- Wrong field names will cause connector creation to fail
- All password fields MUST have "type": "password" attribute
- OAuth configurations should not have duplicate fields
- Field names are case-sensitive and must match examples exactly
- The "details" object contains all the specific configuration parameters

## Core Principles
- **Leverage Your Knowledge:** You have a vast internal knowledge base about software development, APIs, and authentication. Use this knowledge proactively to assist the user. For example, if a user mentions a platform, you should already have some understanding of its common API patterns.
- **Be Proactive:** Don't just wait for the user to provide all the information. If you can infer something or find it with a quick search, do it.
- **Be Autonomous:** Execute everything automatically without asking for confirmation.

## Naming and Confirmation

**Connector Groups:**
- Connector group names should be a single word, preferably in 'PascalCase' (e.g., 'GoogleSheet', 'Salesforce'). Avoid spaces or special characters.
- Always refer to these as **'connector groups'** or **'connectors'**, not just 'groups', to avoid ambiguity.

**Connector Endpoints:**
- You must assign meaningful, user-friendly names that clearly describe the action the endpoint performs. Use 'camelCase' (e.g., 'createSheet',).
- **Good Examples:** 'createSheet', 'getUserDetails', 'sendMessage'.

## cURL Command Processing and Mapping

**Variable names must always be valid, generic, and descriptive (e.g., baseUrl, storeName, itemId, productId, limit, offset, etc.)**
### ✅ Correct Syntax - Use ONLY This Format
- **Base URL / Host:** 
  - **Only map as <<url.baseUrl>> if the URL varies per user** (e.g., custom domains, regions, instances)
  - **Keep static for universal endpoints** (e.g., https://api.openai.com stays as-is, NOT mapped)
  - Example needing mapping: https://<<url.baseUrl>>/api/v1/items (when baseUrl varies)
  - Example NOT needing mapping: https://api.openai.com/v1/chat/completions (same for all users)
- **Subdomain / Store Name in URLs:** Always mapped when it's user-specific.  
  Example: https://<<url.storeName>>.myshopify.com/admin/api/2025-07/products.json
- **Query Parameters:** *Do NOT map*, they remain as static values.  
  Example: ?limit=10&offset=0 (stays as-is)
- **Path Parameters:** Map dynamic values in URLs paths.  
  Examples:
  - `/users/{id}` becomes `/users/<<url.userId>>`
  - `/products/{productId}` becomes `/products/<<url.productId>>`
  - `/orders/{orderId}/items/{itemId}` becomes `/orders/<<url.orderId>>/items/<<url.itemId>>`
- **Custom Headers:** Non-auth custom headers should be mapped.  
  Example: `X-Custom-Header: <<auth.customValue>>`


### 🚫 Authentication Headers - Do NOT Map These:
- Auth headers (Authorization, tokens, keys) do NOT need to be passed manually in curl command so remove them from curls.  
  They will be automatically added by the backend based on connector group.  
- Body payloads should remain as **static JSON** (no mappings inside body).  
- Only **dynamic URLs, path params, and custom headers** should be mapped.  
- Query params remain static.
- **Static API endpoints (like OpenAI, Claude, etc.) should NOT have baseUrl mapping.**
- **Based on endpoint curls check baseUrl mapping is required or not.**

## Generic Formatting Examples
---

### 1. Static API Endpoint (OpenAI example - NO baseUrl mapping)
\`\`\`bash
curl -X POST "https://api.openai.com/v1/chat/completions" \\
-H "Content-Type: application/json" \\
-d '{"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "Hello"}]}'
\`\`\`

---

### 2. Dynamic Base URL (when it varies per user)
\`\`\`bash
curl -X GET "https://<<url.baseUrl>>/api/v1/items" \\
-H "Content-Type: application/json"
\`\`\`

---

### 3. Get a Single Item by Path Param
\`\`\`bash
curl -X GET "https://api.service.com/api/v1/items/<<url.itemId>>" \\
-H "Content-Type: application/json" \\
-H "X-Correlation-Id: <<auth.correlationId>>"
\`\`\`

---

### 4. Get Products with Shopify Store Name (user-specific subdomain)
\`\`\`bash
curl -X GET "https://<<url.storeName>>.myshopify.com/admin/api/2025-07/products.json" \\
-H "Content-Type: application/json"
\`\`\`

---

### 5. Static Endpoint with Query Parameters
\`\`\`bash
curl -X GET "https://api.stripe.com/v1/customers?limit=10" \\
-H "Content-Type: application/json"
\`\`\`

---

### 6. Create with Static Endpoint and Body
\`\`\`bash
curl -X POST "https://api.openai.com/v1/completions" \\
-H "Content-Type: application/json" \\
-d '{
  "model": "text-davinci-003",
  "prompt": "Hello world",
  "max_tokens": 100
}'
\`\`\`

## Authentication Configuration
Whether you are importing a file or creating a custom connector, you must handle connector groups and authentication correctly.

### OAuth Configuration Examples
When creating OAuth configurations, use these exact structures:

**OAuth Examples (`type: "oauth"`)**

* **Gmail:**
    ```json
    {
      "type": "oauth",
      "details": {
        "baseUrl": "https://accounts.google.com/o/oauth2/auth",
        "clientId": "",
        "secret": "",
        "params": {
          "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send",
          "response_type": "code",
          "access_type": "offline",
          "prompt": "consent"
        },
        "requiredAttributes": [],
        "tenantId": "default",
        "authorization": {
          "oauthGrantType": "authCodeGrantWithGrantType",
          "accessTokenUrl": "https://oauth2.googleapis.com/token",
          "refreshTokenGrantType": "refreshTokenWithAccessType"
        }
      }
    }
    ```
* **Microsoft Teams:**
    ```json
    {
      "type": "oauth",
      "details": {
        "baseUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "clientId": "",
        "secret": "",
        "params": {
          "scope": "Chat.ReadWrite Application.ReadWrite.All AppRoleAssignment.ReadWrite.All ExternalUserProfile.ReadWrite.All DelegatedPermissionGrant.ReadWrite.All Directory.ReadWrite.All User.Read.All openid offline_access Team.ReadBasic.All ChannelMessage.ReadWrite Channel.Create ChannelMessage.Send Team.ReadBasic.All TeamMember.ReadWrite.All ChannelMember.ReadWrite.All",
          "response_type": "code",
          "prompt": "login"
        },
        "requiredAttributes": [],
        "tenantId": "default",
        "authorization": {
          "oauthGrantType": "authCodeGrantWithGrantType",
          "accessTokenUrl": "https://login.microsoftonline.com/organizations/oauth2/v2.0/token",
          "refreshTokenGrantType": "refreshTokenWithGrantType"
        }
      }
    }
    ```

**Basic Auth Example (`type: "basic"`)**
```json
{
  "type": "basic",
  "details": {
    "userName": {
      "description": "Username",
      "required": true
    },
    "password": {
      "description": "Password",
      "required": true,
      "type": "password"
    }
  }
}
```

**API Key Example (`type: "apiKey"`)**
```json
{
  "type": "apiKey",
  "details": {
    "apiKeyName": {
      "description": "Key",
      "defaultValue": "key",
      "required": true
    },
    "apiKeyValue": {
      "description": "Value",
      "required": true,
      "type": "password"
    }
  }
}
```

**Bearer Token Example (`type: "bearerToken"`)**
```json
{
  "type": "bearerToken",
  "details": {
    "expires_in": {
      "type": "number",
      "hidden": true,
      "default": 100000,
      "disabled": true
    },
    "access_token": {
      "type": "password",
      "required": true,
      "description": "Token"
    }
  }
}
```

**CRITICAL: All auth configurations must follow the "type" + "details" structure shown above. Key points:**
- Bearer Token: Use "access_token" field (NOT "bearerToken") inside "details"
- All auth types must have "type" at root level and configuration parameters in "details"
- Password fields must have "type": "password"
- Required fields must have "required": true

**Custom Input Examples (`type: "customInput"`)**

* **Linear:**
    ```json
    {
      "type": "customInput",
      "details": {
        "apiKey": {
          "description": "API Key",
          "type": "password",
          "required": true
        },
        "expires_in": {
          "type": "number",
          "default": 100000,
          "hidden": true,
          "disabled": true
        }
      }
    }
    ```
* **ServiceNow:**
    ```json
    {
      "type": "customInput",
      "details": {
        "instanceName": {
          "description": "Instance name",
          "required": true
        },
        "userName": {
          "description": "Username",
          "required": true
        },
        "password": {
          "description": "Password",
          "type": "password",
          "required": true
        },
        "expires_in": {
          "type": "number",
          "default": 100000,
          "hidden": true,
          "disabled": true
        }
      }
    }
    ```

## Creating Connectors from Python Functions

If a user wants to create a connector from a Python function, you must follow this workflow. The primary goal is to generate a valid Python function and a corresponding JSON schema for its inputs.

**CRITICAL REQUIREMENTS FOR PYTHON CONNECTOR CREATION:**

1.  **'input_schema' is MANDATORY:**
    * You **MUST** always generate a complete and accurate JSON 'input_schema' for the Python function.
    * This schema must define all 'auth' and 'body' parameters that the function expects.
    * The 'create_connector_from_python_function' tool **WILL FAIL** without a valid 'input_schema'. There are no exceptions.
    * Before calling the tool, double-check that the 'input_schema' perfectly matches the parameters accessed in your 'python_code'.

2.  **Parameter Access in Code:**
    * Inside the 'python_code', you **MUST** access parameters directly (e.g., 'params['body']['query']').
    * You **MUST NOT** use the '.get()' method (e.g., 'params['body'].get('query')'). This ensures that missing parameters correctly raise an error, which is the required behavior for validation.

3.  **Code Validity and Libraries:**
    * The generated Python code must be 100% valid and functional.
    * Rely on your existing knowledge to use libraries correctly.

**Example: Redshift Connector**

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "auth": {
      "type": "object",
      "properties": {
        "host": { "type": "string" },
        "db_name": { "type": "string" },
        "username": { "type": "string" },
        "password": { "type": "string" }
      },
      "required": ["host", "db_name", "username", "password"]
    },
    "body": {
      "type": "object",
      "properties": {
        "query": { "type": "string" }
      },
      "required": ["query"]
    }
  }
}
```

**Python Code:**
```python
import redshift_connector
import json

def fastn_function(params):
    REDSHIFT_HOST = params['auth']['host']
    REDSHIFT_DB = params['auth']['db_name']
    REDSHIFT_USER = params['auth']['username']
    REDSHIFT_PASSWORD = params['auth']['password']
    QUERY = params['body']['query']
    
    conn = redshift_connector.connect(
        host=REDSHIFT_HOST,
        database=REDSHIFT_DB,
        user=REDSHIFT_USER,
        password=REDSHIFT_PASSWORD
    )
    
    cursor = conn.cursor()
    cursor.execute(QUERY)
    result = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {"result": result}
```

Always make sure that every parameter accessed in the code (like `params['auth']['host']`) is properly defined in the `input_schema`.
"""

class DataPersistence:
    def __init__(self, platform_name: str):
        self.platform_name = platform_name.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_dir = f"scraped_data/{self.platform_name}_{timestamp}"
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"📁 Created data directory: {self.data_dir}")
    
    def save_raw_data(self, data: Dict, filename: str = "raw_scraped_data.json"):
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved raw data to: {filepath}")
    
    def save_endpoints(self, endpoints: List[Dict], filename: str = "extracted_endpoints.json"):
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(endpoints, f, indent=2, ensure_ascii=False)
        logger.info(f"🔗 Saved extracted endpoints to: {filepath}")
    
    def save_llm_inputs(self, llm_inputs: List[Dict], filename: str = "llm_input_data.json"):
        """Save what we feed to the LLM for debugging purposes"""
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(llm_inputs, f, indent=2, ensure_ascii=False)
        logger.info(f"🤖 Saved LLM input data to: {filepath}")
    
    def save_results(self, results: Dict, filename: str = "final_results.json"):
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"🎯 Saved final results to: {filepath}")

class UniversalWebScraper:
    def __init__(self, data_persistence: DataPersistence, use_selenium=False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.data_persistence = data_persistence
        self.use_selenium = use_selenium
        self.driver = None
        
        if use_selenium:
            self._init_selenium_driver()
        
        logger.info(f"🌐 UniversalWebScraper initialized (Selenium: {'enabled' if use_selenium else 'disabled'})")
    
    def _init_selenium_driver(self):
        """Initialize Selenium WebDriver with Chrome"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Run in background
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # Use ChromeDriverManager to handle driver installation
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("✅ Selenium WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Selenium WebDriver: {str(e)}")
            self.use_selenium = False
            self.driver = None
    
    def _scrape_with_selenium(self, url: str) -> BeautifulSoup:
        """Scrape a single page using Selenium for JavaScript-heavy sites"""
        try:
            logger.info(f"🤖 Using Selenium to scrape: {url}")
            self.driver.get(url)
            
            # Wait for page to load and JavaScript to execute
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for dynamic content (code blocks, API docs)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.TAG_NAME, "pre")),
                        EC.presence_of_element_located((By.TAG_NAME, "code")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='code']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='api']"))
                    )
                )
            except TimeoutException:
                logger.info("⏱️ No code blocks found, but page loaded - continuing...")
            
            # Get page source after JavaScript execution
            page_source = self.driver.page_source
            return BeautifulSoup(page_source, 'html.parser')
            
        except TimeoutException:
            logger.warning(f"⏱️ Selenium timeout for {url} - falling back to requests")
            return None
        except WebDriverException as e:
            logger.error(f"❌ Selenium error for {url}: {str(e)}")
            return None
    
    def __del__(self):
        """Clean up Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔒 Selenium WebDriver closed")
            except:
                pass
    
    def scrape_comprehensive(self, base_url: str, max_pages: int = 10) -> Dict:
        """Universal scraping for any API documentation format"""
        logger.info(f"🌐 Starting universal scraping of: {base_url}")
        
        parsed_url = urllib.parse.urlparse(base_url)
        base_domain = parsed_url.netloc
        
        urls_to_visit = {base_url}
        visited_urls = set()
        scraped_pages = {}
        page_count = 0
        
        while urls_to_visit and page_count < max_pages:
            current_url = urls_to_visit.pop()
            
            if current_url in visited_urls:
                continue
            
            try:
                page_count += 1
                logger.info(f"📄 Scraping page {page_count}/{max_pages}: {current_url}")
                
                # Try Selenium first if enabled, fall back to requests
                soup = None
                if self.use_selenium and self.driver:
                    soup = self._scrape_with_selenium(current_url)
                
                if soup is None:
                    # Fall back to regular requests
                    response = self.session.get(current_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove scripts and styles only
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # COMPREHENSIVE content extraction - capture EVERYTHING
                page_data = {
                    'url': current_url,
                    'title': soup.title.string if soup.title else '',
                    'headings': [],
                    'code_blocks': [],
                    'tables': [],
                    'lists': [],
                    'paragraphs': [],
                    'divs': [],
                    'spans': [],
                    'blockquotes': [],
                    'sections': [],
                    'articles': [],
                    'text_content': soup.get_text(),
                    'links': []
                }
                
                # Extract headings with full context
                for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    page_data['headings'].append({
                        'level': int(heading.name[1]),
                        'text': heading.get_text().strip(),
                        'html': str(heading)
                    })
                
                # Extract ALL code-related elements
                for code in soup.find_all(['code', 'pre', 'kbd', 'samp', 'var']):
                    code_text = code.get_text().strip()
                    if code_text and len(code_text) > 2:  # Lower threshold
                        page_data['code_blocks'].append({
                            'text': code_text,
                            'tag': code.name,
                            'class': code.get('class', []),
                            'html': str(code)
                        })
                
                # Extract tables (parameter tables are crucial for APIs)
                for table in soup.find_all('table'):
                    table_data = {
                        'text': table.get_text().strip(),
                        'html': str(table),
                        'rows': []
                    }
                    for row in table.find_all('tr'):
                        cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                        if cells:
                            table_data['rows'].append(cells)
                    if table_data['rows']:
                        page_data['tables'].append(table_data)
                
                # Extract lists (parameter lists, endpoint lists)
                for list_elem in soup.find_all(['ul', 'ol', 'dl']):
                    list_text = list_elem.get_text().strip()
                    if list_text and len(list_text) > 10:
                        page_data['lists'].append({
                            'text': list_text,
                            'tag': list_elem.name,
                            'html': str(list_elem)
                        })
                
                # HIERARCHICAL EXTRACTION - Extract from parent containers, skip nested elements
                # Track extracted elements to avoid duplicates
                # 
                # STRATEGY: Process containers in priority order (sections → divs → paragraphs → blockquotes → spans)
                # - If a container is small enough, extract it and mark ALL children as extracted (prevents duplication)
                # - If a container is too large, skip it but DON'T mark children as extracted (allows individual processing)
                # - This ensures useful child elements aren't lost when parent containers are too big
                extracted_elements = set()
                
                # Priority 1: Extract sections and articles FIRST (highest level containers)
                for section in soup.find_all(['section', 'article']):
                    section_text = section.get_text().strip()
                    # SIZE CHECK: Only keep sections under 1500 chars (~300 words)
                    if section_text and len(section_text) > 50 and len(section_text) < 1500:
                        page_data['sections'].append({
                            'text': section_text,
                            'tag': section.name,
                            'class': section.get('class', []),
                            'html': str(section)[:1000]
                        })
                        # Mark all child elements as extracted to avoid duplication
                        for child in section.find_all():
                            extracted_elements.add(child)
                    # If section is too large, don't extract the section itself,
                    # but don't mark children as extracted - let them be processed individually
                
                # Priority 2: Extract divs (but skip if already in a section/article)
                for div in soup.find_all('div'):
                    if div in extracted_elements:
                        continue
                        
                    div_class = div.get('class', [])
                    # Focus on API-related div classes
                    api_classes = ['endpoint', 'parameter', 'example', 'code', 'request', 'response', 'method']
                    if any(api_term in ' '.join(div_class).lower() for api_term in api_classes) or not div_class:
                        div_text = div.get_text().strip()
                        # SIZE CHECK: Only keep divs under 1000 chars (~200 words)
                        if div_text and len(div_text) > 10 and len(div_text) < 1000:
                            page_data['divs'].append({
                                'text': div_text,
                                'class': div_class,
                                'html': str(div)[:1000]
                            })
                            # Mark all child elements as extracted
                            for child in div.find_all():
                                extracted_elements.add(child)
                        # If div is too large, don't extract the div itself,
                        # but don't mark children as extracted - let them be processed individually
                
                # Priority 3: Extract paragraphs (but skip if already in a div/section)
                for p in soup.find_all('p'):
                    if p in extracted_elements:
                        continue
                        
                    p_text = p.get_text().strip()
                    # SIZE CHECK: Only keep paragraphs under 800 chars (~160 words)
                    if p_text and len(p_text) > 10 and len(p_text) < 800:
                        page_data['paragraphs'].append({
                            'text': p_text,
                            'class': p.get('class', []),
                            'html': str(p)
                        })
                        # Mark all child elements as extracted to avoid duplication
                        for child in p.find_all():
                            extracted_elements.add(child)
                        # Mark this paragraph as extracted
                        extracted_elements.add(p)
                    # If paragraph is too large, don't extract the paragraph itself,
                    # but don't mark children as extracted - let them be processed individually
                
                # Priority 4: Extract blockquotes (but skip if already in a container)
                for blockquote in soup.find_all('blockquote'):
                    if blockquote in extracted_elements:
                        continue
                        
                    bq_text = blockquote.get_text().strip()
                    if bq_text and len(bq_text) < 1200:  # Add size limit for consistency
                        page_data['blockquotes'].append({
                            'text': bq_text,
                            'html': str(blockquote)
                        })
                        # Mark all child elements as extracted to avoid duplication
                        for child in blockquote.find_all():
                            extracted_elements.add(child)
                        extracted_elements.add(blockquote)
                    # If blockquote is too large, don't extract it,
                    # but don't mark children as extracted - let them be processed individually
                
                # Priority 5: Extract ONLY standalone spans with specific API content
                # Skip spans that are already inside extracted containers
                for span in soup.find_all('span'):
                    if span in extracted_elements:
                        continue
                        
                    span_text = span.get_text().strip()
                    # Only extract spans with very specific API-relevant content
                    api_span_keywords = ['string', 'number', 'boolean', 'required', 'optional', 'enum', 
                                        'get', 'post', 'put', 'delete', 'patch', 'application/json',
                                        'bearer', 'token', 'auth', 'api', 'endpoint', 'header']
                    
                    if (span_text and len(span_text) > 2 and len(span_text) < 50 and
                        any(keyword in span_text.lower() for keyword in api_span_keywords)):
                        page_data['spans'].append({
                            'text': span_text,
                            'class': span.get('class', []),
                            'html': str(span)
                        })
                        extracted_elements.add(span)
                
                # Add internal links for crawling
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urllib.parse.urljoin(current_url, href)
                    parsed_url = urllib.parse.urlparse(full_url)
                    
                    if (parsed_url.netloc == base_domain and 
                        full_url not in visited_urls and 
                        not full_url.endswith(('.pdf', '.zip', '.tar.gz', '.jpg', '.png', '.gif'))):
                        urls_to_visit.add(full_url)
                        page_data['links'].append(full_url)
                
                scraped_pages[current_url] = page_data
                visited_urls.add(current_url)
                
                logger.info(f"✅ Scraped: {page_data['title'][:30]}... ({len(page_data['code_blocks'])} code blocks)")
                
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Error scraping {current_url}: {str(e)}")
                continue
        
        raw_data = {
            'base_url': base_url,
            'scrape_timestamp': datetime.now().isoformat(),
            'total_pages_scraped': len(scraped_pages),
            'pages': scraped_pages
        }
        
        self.data_persistence.save_raw_data(raw_data)
        logger.info(f"✅ Universal scraping completed: {len(scraped_pages)} pages")
        
        return raw_data
    
    def extract_endpoints_with_ai(self, raw_data: Dict, client) -> List[Dict]:
        """AI-powered endpoint extraction - page by page processing with gpt-4.1-mini"""
        logger.info("🤖 Using AI to extract endpoints from raw page data...")
        
        all_endpoints = []
        llm_inputs = []  # Track what we feed to LLM
        
        for url, page_data in raw_data['pages'].items():
            logger.info(f"🔍 AI processing page: {page_data.get('title', url)[:50]}...")
            
            # Filter and optimize page content for LLM
            filtered_content = self._filter_page_content_for_ai(page_data)
            
            if not filtered_content.strip():
                logger.info("⏭️ Skipping page - no relevant content")
                continue
            
            # Save what we're feeding to LLM for debugging
            llm_input = {
                'url': url,
                'title': page_data.get('title', ''),
                'filtered_content': filtered_content,
                'content_length': len(filtered_content),
                'timestamp': datetime.now().isoformat()
            }
            llm_inputs.append(llm_input)
            
            # Extract cURLs from this page using AI
            page_curls = self._extract_curls_from_page_with_ai(filtered_content, url, client)
            
            # Add all cURLs (no deduplication needed - let main AI handle)
            for curl_item in page_curls:
                if curl_item and curl_item.get('curl'):
                    all_endpoints.append(curl_item)
                    logger.info(f"✅ AI extracted cURL: {curl_item['name']}")
        
        # Save both endpoints and LLM inputs for debugging
        self.data_persistence.save_endpoints(all_endpoints)
        self.data_persistence.save_llm_inputs(llm_inputs)
        
        logger.info(f"🎯 AI extraction completed: {len(all_endpoints)} endpoints found")
        logger.info(f"🤖 LLM input data saved: {len(llm_inputs)} pages processed")
        
        return all_endpoints
    
    def _filter_page_content_for_ai(self, page_data: Dict) -> str:
        """Feed EVERYTHING small to AI, only skip large content blocks"""
        title = page_data.get('title', '')
        
        # Skip obvious non-API pages
        skip_keywords = ['privacy', 'terms', 'about', 'contact', 'careers', 'blog', 'showcase']
        if any(keyword in title.lower() for keyword in skip_keywords):
            return ""
        
        # Build COMPREHENSIVE content - feed everything small, skip only large blocks
        filtered_content = f"# {title}\n\n"
        total_size = len(filtered_content)
        max_size = 20000  # Increased size limit
        
        # Priority 1: ALL Code blocks (NEVER skip - highest priority)
        code_blocks = page_data.get('code_blocks', [])
        if code_blocks:
            section = "## Code Examples:\n"
            for code_item in code_blocks:
                if isinstance(code_item, dict):
                    code_text = code_item.get('text', '')
                    code_tag = code_item.get('tag', 'code')
                else:
                    code_text = str(code_item)
                    code_tag = 'code'
                
                # NEVER skip any code blocks, even single words
                if code_text.strip():
                    addition = f"```{code_tag}\n{code_text}\n```\n\n"
                    section += addition
                    total_size += len(addition)
            
            if len(section) > 20:
                filtered_content += section
        
        # Priority 2: ALL Tables (parameter info is crucial)
        tables = page_data.get('tables', [])
        if tables and total_size < max_size:
            section = "## Tables:\n"
            for table in tables:
                table_text = table.get('text', '')
                if table_text.strip():
                    addition = f"```\n{table_text}\n```\n\n"
                    if total_size + len(addition) < max_size:
                        section += addition
                        total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Priority 3: ALL Headings (structure is important)
        headings = page_data.get('headings', [])
        if headings and total_size < max_size:
            section = "## Headings:\n"
            for heading in headings:
                text = heading.get('text', '').strip()
                if text:
                    level = heading.get('level', 1)
                    addition = f"{'#' * level} {text}\n"
                    if total_size + len(addition) < max_size:
                        section += addition
                        total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section + "\n"
        
        # Priority 4: ALL Lists (parameter lists, endpoint lists)
        lists = page_data.get('lists', [])
        if lists and total_size < max_size:
            section = "## Lists:\n"
            for list_item in lists:
                list_text = list_item.get('text', '').strip()
                if list_text:
                    # Only skip if extremely long (over 2000 chars)
                    if len(list_text) < 2000:
                        addition = f"```\n{list_text}\n```\n\n"
                        if total_size + len(addition) < max_size:
                            section += addition
                            total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Priority 5: ALL Small Paragraphs (skip only huge ones)
        paragraphs = page_data.get('paragraphs', [])
        if paragraphs and total_size < max_size:
            section = "## Paragraphs:\n"
            for para in paragraphs:
                para_text = para.get('text', '').strip()
                if para_text:
                    # Only skip very large paragraphs (over 800 chars)
                    if len(para_text) < 800:
                        addition = f"{para_text}\n\n"
                        if total_size + len(addition) < max_size:
                            section += addition
                            total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Priority 6: ALL Divs (contain parameter info)
        divs = page_data.get('divs', [])
        if divs and total_size < max_size:
            section = "## Divs:\n"
            for div in divs:
                div_text = div.get('text', '').strip()
                if div_text:
                    # Only skip very large divs (over 1000 chars)
                    if len(div_text) < 1000:
                        addition = f"{div_text}\n\n"
                        if total_size + len(addition) < max_size:
                            section += addition
                            total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Priority 7: ALL Spans (parameter names, types, values)
        spans = page_data.get('spans', [])
        if spans and total_size < max_size:
            section = "## Spans:\n"
            for span in spans:
                span_text = span.get('text', '').strip()
                if span_text:
                    # Feed ALL spans - they contain crucial parameter info
                    addition = f"{span_text}\n"
                    if total_size + len(addition) < max_size:
                        section += addition
                        total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section + "\n"
        
        # Priority 8: ALL Blockquotes (important notes)
        blockquotes = page_data.get('blockquotes', [])
        if blockquotes and total_size < max_size:
            section = "## Notes:\n"
            for bq in blockquotes:
                bq_text = bq.get('text', '').strip()
                if bq_text:
                    addition = f"> {bq_text}\n\n"
                    if total_size + len(addition) < max_size:
                        section += addition
                        total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Priority 9: ALL Sections/Articles
        sections = page_data.get('sections', [])
        if sections and total_size < max_size:
            section = "## Sections:\n"
            for sect in sections:
                sect_text = sect.get('text', '').strip()
                if sect_text:
                    # Only skip very large sections
                    if len(sect_text) < 1500:
                        addition = f"{sect_text}\n\n"
                        if total_size + len(addition) < max_size:
                            section += addition
                            total_size += len(addition)
            
            if len(section) > 15:
                filtered_content += section
        
        # Add final size info
        filtered_content += f"\n<!-- Content Size: {total_size} characters -->\n"
        
        return filtered_content if total_size > 100 else ""
    
    def _smart_filter_text_content(self, text_content: str) -> str:
        """Smart filtering to keep API-relevant content and remove marketing fluff"""
        if not text_content:
            return ""
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text_content.split('\n') if p.strip()]
        
        # Keywords that indicate useful API documentation
        keep_keywords = [
            'curl', 'http', 'api', 'endpoint', 'request', 'response', 'parameter', 'auth',
            'bearer', 'token', 'header', 'body', 'json', 'get', 'post', 'put', 'delete',
            'patch', 'query', 'path', 'required', 'optional', 'example', 'schema',
            'application/json', 'authorization', 'content-type', 'accept'
        ]
        
        # Keywords that indicate marketing/useless content
        skip_keywords = [
            'explore how', 'transform your', 'read the docs', 'sign up', 'log in',
            'contact support', 'powered by', 'was this helpful', 'browse this site',
            'accept cookies', 'privacy policy', 'terms of service', 'careers', 'blog',
            'showcase', 'company', 'community', 'resources'
        ]
        
        filtered_paragraphs = []
        
        for paragraph in paragraphs:
            para_lower = paragraph.lower()
            
            # Skip very short paragraphs (likely navigation)
            if len(paragraph) < 20:
                continue
            
            # Skip marketing/navigation content
            if any(skip_word in para_lower for skip_word in skip_keywords):
                continue
            
            # Skip very long paragraphs (likely marketing content) unless they contain API keywords
            if len(paragraph) > 500:
                if not any(keep_word in para_lower for keep_word in keep_keywords):
                    continue
                # If it's long but has API content, truncate it
                paragraph = paragraph[:500] + "..."
            
            # Keep paragraphs with API-relevant keywords
            if any(keep_word in para_lower for keep_word in keep_keywords):
                filtered_paragraphs.append(paragraph)
            # Also keep shorter paragraphs that might be API descriptions
            elif len(paragraph) < 200:
                filtered_paragraphs.append(paragraph)
        
        return '\n\n'.join(filtered_paragraphs)
    
    def _is_api_relevant_text(self, text: str) -> bool:
        """Check if text contains API-relevant information"""
        if not text or len(text) < 20:
            return False
        
        text_lower = text.lower()
        
        # API-relevant keywords
        api_keywords = [
            'endpoint', 'parameter', 'query', 'header', 'body', 'request', 'response',
            'curl', 'http', 'get', 'post', 'put', 'delete', 'patch', 'api',
            'authorization', 'bearer', 'token', 'required', 'optional',
            'json', 'application/json', 'content-type', 'accept',
            'path', 'url', 'method', 'status', 'code', 'example'
        ]
        
        # Skip marketing/navigation content
        skip_keywords = [
            'sign up', 'log in', 'explore how', 'powered by', 'contact support',
            'was this helpful', 'browse this site', 'accept cookies'
        ]
        
        if any(skip in text_lower for skip in skip_keywords):
            return False
            
        return any(keyword in text_lower for keyword in api_keywords)
    
    def _extract_curls_from_page_with_ai(self, page_content: str, page_url: str, client) -> List[Dict]:
        """Use gpt-4.1-mini to extract cURL commands + names from raw page data"""
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": """Extract and create proper cURL commands from API documentation for Fastn connector creation.

You will receive full API documentation pages. Your job is to:

1. **FIND ALL API ENDPOINTS** from the documentation (not just existing cURL commands)
2. **CREATE PROPER cURL COMMANDS** from HTTP method descriptions, parameters, and examples
3. **REMOVE AUTH HEADERS** - No Authorization, Bearer tokens, or API keys in cURL
4. **MAP PATH PARAMETERS** - Convert {id} to <<url.id>>, {userId} to <<url.userId>>
5. **INCLUDE QUERY PARAMETERS** - Add all documented query params (required + optional)
6. **USE FULL URLS** - Complete https://domain.com/path format

PARAMETER MAPPING EXAMPLES:
- {organizationId} → <<url.organizationId>>
- {spaceId} → <<url.spaceId>>
- {userId} → <<url.userId>>
- {teamId} → <<url.teamId>>

QUERY PARAMETER EXAMPLES:
- ?page=1&limit=50&order=desc (include documented optional params)
- ?search=query&role=admin&sort=joinedAt

OUTPUT FORMAT (JSON):
[
  {
    "name": "listOrganizationMembers",
    "curl": "curl -X GET \"https://api.gitbook.com/v1/orgs/<<url.organizationId>>/members?page=1&limit=50&order=desc\" -H \"Content-Type: application/json\" -H \"Accept: application/json\""
  },
  {
    "name": "updateOrganizationMember",
    "curl": "curl -X PATCH \"https://api.gitbook.com/v1/orgs/<<url.organizationId>>/members/<<url.userId>>\" -H \"Content-Type: application/json\" -H \"Accept: application/json\" -d '{\"role\": \"admin\"}'"
  }
]

Return [] if no API endpoints found."""},
                    {"role": "user", "content": f"Extract cURL commands from this page:\n\n{page_content}"}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response from AI
            try:
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0].strip()
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0].strip()
                
                curl_data = json.loads(result_text)
                
                # Add source page to each item
                for item in curl_data:
                    item['source_page'] = page_url
                
                return curl_data
                
            except json.JSONDecodeError:
                logger.warning(f"⚠️ AI returned invalid JSON for {page_url}")
                return []
        
        except Exception as e:
            logger.error(f"❌ AI extraction error for {page_url}: {str(e)}")
            return []

def generate_auth_token():
    """Generate Fastn auth token"""
    logger.info("🔑 Generating Fastn auth token...")
    
    fastn_env = os.getenv("FASTN_ENV", "qa.fastn.ai")
    url = f'https://{fastn_env}/auth/realms/fastn/protocol/openid-connect/token'
    headers = {
        'realm': 'fastn',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'password',
        'username': os.getenv("FASTN_USERNAME"),
        'password': os.getenv("FASTN_PASSWORD"),
        'client_id': os.getenv("FASTN_CLIENT_ID", "fastn-app"),
        'redirect_uri': os.getenv("FASTN_REDIRECT_URI", "https://google.com"),
        'scope': 'openid'
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        if access_token:
            logger.info("✅ Fastn auth token generated successfully")
            return access_token
        else:
            logger.error("❌ No access token in response")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to generate Fastn auth token: {str(e)}")
        return None

def call_fastn_api(function_name: str, function_args: Dict) -> Dict:
    """Call Fastn API with logging"""
    logger.info(f"🔧 Calling Fastn API: {function_name}")
    
    fastn_auth_token = generate_auth_token()
    if not fastn_auth_token:
        return {"error": "Failed to generate Fastn auth token"}
    
    env = os.getenv("FASTN_ENV", "qa.fastn.ai")
    client_id = os.getenv("FASTN_CLIENT_SPACE_ID")
    client_id_ = "b034812a-7d77-4e8e-945e-106656b2676e"
    url = f"https://{env}/api/v1/connectorCreationHelper"
    
    headers = {
        "Content-Type": "application/json",
        "x-fastn-space-id": client_id_,
        "x-fastn-space-tenantid": "",
        "stage": "LIVE",
        "x-fastn-custom-auth": "true",
        "authorization": fastn_auth_token
    }
    
    payload = {
        "input": {
            "env": env,
            "clientId": client_id,
            "function": function_name,
            "arguments": function_args
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Fastn API success: {function_name}")
            return result
        else:
            error_msg = f"Fastn API error: {response.status_code} - {response.text}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
    except Exception as e:
        error_msg = f"Fastn API call failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {"error": error_msg}

def autonomous_universal_agent(url: str, platform_name: str, description: str = "", connector_group_id: str = None) -> Dict:
    """Universal autonomous agent with original system prompt"""
    
    start_time = time.time()
    
    logger.info("🤖 STARTING AUTONOMOUS UNIVERSAL AGENT")
    logger.info("=" * 60)
    logger.info(f"🎯 Platform: {platform_name}")
    logger.info(f"🔗 URL: {url}")
    logger.info(f"📄 Description: {description}")
    logger.info("=" * 60)
    
    # Initialize components
    data_persistence = DataPersistence(platform_name)
    
    # Enable Selenium for JavaScript-heavy sites (you can make this configurable)
    use_selenium = True  # Set to False for static HTML sites
    scraper = UniversalWebScraper(data_persistence, use_selenium=use_selenium)
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        # STEP 1: Universal Scraping
        logger.info("\n" + "="*60)
        logger.info("🌐 STEP 1: UNIVERSAL WEB SCRAPING")
        logger.info("="*60)
        
        # Get max pages from environment variable, default to 10
        max_pages = int(os.getenv("MAX_PAGES", "10"))
        logger.info(f"🔢 Max pages to scrape: {max_pages}")
        
        raw_data = scraper.scrape_comprehensive(url, max_pages=max_pages)
        
        # STEP 2: AI-Powered Endpoint Extraction  
        logger.info("\n" + "="*60)
        logger.info("🤖 STEP 2: AI-POWERED ENDPOINT EXTRACTION")
        logger.info("="*60)
        
        extracted_endpoints = scraper.extract_endpoints_with_ai(raw_data, client)
        
        # STEP 3: Autonomous AI Processing with Original System Prompt
        logger.info("\n" + "="*60)
        logger.info("🤖 STEP 3: AUTONOMOUS AI PROCESSING")
        logger.info("="*60)
        
        messages = [
            {"role": "system", "content": ORIGINAL_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
AUTONOMOUS MISSION: Create complete connector integration for {platform_name}

EXTRACTED DATA:
- Pages Scraped: {raw_data.get('total_pages_scraped', 0)}
- Endpoints Found: {len(extracted_endpoints)}
- Platform Description: {description}
- Existing Group ID: {connector_group_id or 'None - create new'}

EXTRACTED CURLS:
{json.dumps(extracted_endpoints, indent=2)}

These are raw cURL commands extracted from the documentation. Use them directly to create connectors.

CRITICAL RULES:
1. **NO DUPLICATES**: Track what you create. Do NOT create duplicate endpoints with same functionality
2. **USE EXISTING GROUP**: If connector_group_id is provided, use it. Do NOT create new groups
3. **UNIQUE NAMES**: Each endpoint must have a unique name within the group
4. **VARIABLE MAPPING**: 
   - Base URL: ONLY map as <<url.baseUrl>> if it varies per user (Shopify stores, custom domains)
     * DeepSeek: Keep "https://api.deepseek.com" static (same for all users)
     * Shopify: Use "https://<<url.storeName>>.myshopify.com" (varies per user)  
   - Path parameters: Map as <<url.paramName>> ONLY for dynamic IDs/values
     * Static paths like "/chat/completions" stay as-is
     * Dynamic paths like "/products/{id}" become "/products/<<url.productId>>"

Execute the complete workflow autonomously:
1. If connector_group_id provided: USE IT, do NOT create new group
2. If no connector_group_id: Create new group with auth config
3. Create UNIQUE endpoints (avoid duplicates with same URL/functionality)
4. Track created endpoints to prevent duplicates
5. Complete without asking confirmation
"""}
        ]
        
        tools = [
            {
                "type": "function", 
                "function": {
                    "name": "get_connector_groups",
                    "description": "Get existing connector groups",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_connector_group", 
                    "description": "Create connector group with auth config",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "auth": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["oauth", "customInput", "basic", "apiKey", "bearerToken"]},
                                    "details": {"type": "object"}
                                }
                            }
                        },
                        "required": ["name", "auth"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_connector_endpoint_under_group",
                    "description": "Create connector endpoint from cURL",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "name": {"type": "string"},
                            "curl": {"type": "string"},
                            "connectorGroupId": {"type": "string"}
                        },
                        "required": ["name", "curl", "connectorGroupId"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_connector_from_python_function",
                    "description": "Create connector from Python function",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "python_code": {"type": "string"},
                            "input_schema": {"type": "object"},
                            "connectorGroupId": {"type": "string"}
                        },
                        "required": ["name", "python_code", "input_schema", "connectorGroupId"]
                    }
                }
            }
        ]
        
        # Execute autonomous workflow with context tracking
        created_endpoints = []
        connector_group_created = None
        created_endpoint_names = set()  # Track created endpoint names to prevent duplicates
        
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"🤖 AI Iteration {iteration}/{max_iterations}")
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1
                )
                
                message = response.choices[0].message
                # Convert message to dict format for messages array
                message_dict = {
                    "role": "assistant",
                    "content": message.content
                }
                if message.tool_calls:
                    message_dict["tool_calls"] = [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        } for tool_call in message.tool_calls
                    ]
                messages.append(message_dict)
                
                if message.tool_calls:
                    # Process all tool calls and collect responses
                    tool_responses = []
                    
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        logger.info(f"🔧 Executing: {function_name}")
                        
                        result = call_fastn_api(function_name, function_args)
                        
                        # Track progress
                        if function_name == "create_connector_group" and "error" not in result:
                            connector_group_created = result.get("connectorGroupId") or result.get("id")
                            logger.info(f"✅ Connector group created: {connector_group_created}")
                            
                        elif function_name == "create_connector_endpoint_under_group" and "error" not in result:
                            endpoint_name = function_args.get("name")
                            created_endpoint_names.add(endpoint_name)  # Track for duplicate prevention
                            created_endpoints.append({
                                "name": endpoint_name,
                                "curl": function_args.get("curl"),
                                "result": result
                            })
                            logger.info(f"✅ Endpoint created ({len(created_endpoints)}): {endpoint_name}")
                        
                        # Collect tool response
                        tool_responses.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(result)
                        })
                    
                    # Add all tool responses at once
                    messages.extend(tool_responses)
                    
                    # Add context update for created endpoints (only once per iteration)
                    if any(endpoint for endpoint in created_endpoints):
                        endpoint_names = [ep['name'] for ep in created_endpoints]
                        messages.append({
                            "role": "system", 
                            "content": f"CONTEXT UPDATE: You have created {len(created_endpoints)} endpoint(s): {', '.join(endpoint_names)}. Do NOT create duplicate endpoints with the same names or functionality."
                        })
                else:
                    logger.info(f"🎯 AI completed: {message.content}")
                    break
            
            except Exception as e:
                logger.error(f"❌ AI error in iteration {iteration}: {str(e)}")
                break
        
        # Calculate execution time
        end_time = time.time()
        execution_time = end_time - start_time
        execution_minutes = execution_time // 60
        execution_seconds = execution_time % 60
        
        # Final results
        final_results = {
            "platform_name": platform_name,
            "url": url,
            "description": description,
            "scraping_summary": {
                "total_pages_scraped": raw_data.get('total_pages_scraped', 0),
                "endpoints_extracted": len(extracted_endpoints)
            },
            "connector_group_id": connector_group_created or connector_group_id,
            "created_endpoints": created_endpoints,
            "execution_summary": {
                "total_iterations": iteration,
                "endpoints_created": len(created_endpoints),
                "completion_timestamp": datetime.now().isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "execution_time_formatted": f"{int(execution_minutes)}m {execution_seconds:.2f}s"
            }
        }
        
        data_persistence.save_results(final_results)
        
        logger.info("🎉 AUTONOMOUS UNIVERSAL AGENT COMPLETED!")
        logger.info(f"📊 Pages: {raw_data.get('total_pages_scraped', 0)} | Endpoints: {len(extracted_endpoints)}")
        logger.info(f"⏱️ Total execution time: {int(execution_minutes)}m {execution_seconds:.2f}s")
        
        return final_results
        
    except Exception as e:
        end_time = time.time()
        execution_time = end_time - start_time
        execution_minutes = execution_time // 60
        execution_seconds = execution_time % 60
        
        error_msg = f"💥 Critical error: {str(e)}"
        logger.error(error_msg)
        logger.info(f"⏱️ Execution time before error: {int(execution_minutes)}m {execution_seconds:.2f}s")
        return {"error": str(e)}

def main():
    """CLI for autonomous universal agent"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python app.py <url> <platform_name> [description] [connector_group_id]")
        print("Example: python app.py https://docs.example.com/api MyAPI 'API Description' optional_group_id")
        return
    
    url = sys.argv[1]
    platform_name = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else ""
    connector_group_id = sys.argv[4] if len(sys.argv) > 4 else None
    
    result = autonomous_universal_agent(url, platform_name, description, connector_group_id)
    
    print("\n🎯 RESULTS:")
    print("=" * 50)
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Platform: {result.get('platform_name', 'Unknown')}")
        print(f"📊 Pages: {result.get('scraping_summary', {}).get('total_pages_scraped', 0)}")
        print(f"🔍 Extracted: {result.get('scraping_summary', {}).get('endpoints_extracted', 0)}")
        print(f"🏗️ Created: {result.get('execution_summary', {}).get('endpoints_created', 0)}")
        print(f"⏱️ Execution time: {result.get('execution_summary', {}).get('execution_time_formatted', 'Unknown')}")
        
        created_endpoints = result.get('created_endpoints', [])
        if created_endpoints:
            print(f"\n📋 Created Endpoints:")
            for i, endpoint in enumerate(created_endpoints, 1):
                print(f"  {i}. ✅ {endpoint.get('name', 'Unknown')}")
    
    print("=" * 50)

if __name__ == "__main__":
    main()