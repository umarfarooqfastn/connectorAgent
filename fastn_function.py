import os
import json
import time
import asyncio
import logging
import requests
from typing import Dict, List
from datetime import datetime
from pydantic import BaseModel, Field, create_model
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai import LLMExtractionStrategy

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
- **Auto-Search When Platform Mentioned:** When user provides ONLY a platform name, IMMEDIATELY and AUTOMATICALLY use search_on_internet to find:
  * Official API documentation URLs
  * Postman collection .json files
  * OpenAPI/Swagger specifications
  * Authentication methods and setup guides (OAuth, Bearer Token, API Key, etc.)
  * Don't ask permission - just do it and present the results
- **Multi-Resource Search:** Always search for multiple resource types simultaneously to give user the best options.
- **Authentication Discovery:** Proactively discover and analyze authentication methods to suggest the optimal auth configuration for the connector group.

## Naming and Confirmation

**Connector Groups:**
- Connector group names should be a single word, preferably in 'PascalCase' (e.g., 'GoogleSheet', 'Salesforce'). Avoid spaces or special characters.
- Always refer to these as **'connector groups'** or **'connectors'**, not just 'groups', to avoid ambiguity.

**Connector Endpoints:**
- You must assign meaningful, user-friendly names that clearly describe the action the endpoint performs. Use 'camelCase' (e.g., 'createSheet',).
- **Good Examples:** 'createSheet', 'getUserDetails', 'sendMessage'.

## cURL Command Processing and Mapping

**Variable names must always be valid, generic, and descriptive (e.g., baseUrl, storeName, itemId, productId, limit, offset, etc.)**

**CRITICAL: Always use single quotes in cURL commands - Never use escaped double quotes**
- ✅ Correct: `curl -X GET 'https://api.example.com' -H 'Content-Type: application/json'`  
- ❌ Wrong: `curl -X GET \"https://api.example.com\" -H \"Content-Type: application/json\"`

### ✅ Correct Syntax - Use ONLY This Format
- **Base URL / Host:** 
  - **Only map as <<auth.baseUrl>> if the URL varies per user** (e.g., custom domains, regions, instances)
  - **Keep static for universal endpoints** (e.g., https://api.openai.com stays as-is, NOT mapped)
  - Example needing mapping: https://<<auth.baseUrl>>/api/v1/items (when baseUrl varies)
  - Example NOT needing mapping: https://api.openai.com/v1/chat/completions (same for all users)
- **Subdomain / Store Name in URLs:** Always mapped when it's user-specific.  
  Example: https://<<auth.storeName>>.myshopify.com/admin/api/2025-07/products.json
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
```bash
curl -X POST 'https://api.openai.com/v1/chat/completions' \
-H 'Content-Type: application/json' \
-d '{"model": "gpt-5-mini", "messages": [{"role": "user", "content": "Hello"}]}'
```

---

### 2. Dynamic Base URL (when it varies per user)
```bash
curl -X GET 'https://<<auth.baseUrl>>/api/v1/items' \
-H 'Content-Type: application/json'
```

---

### 3. Get a Single Item by Path Param
```bash
curl -X GET 'https://api.service.com/api/v1/items/<<url.itemId>>' \
-H 'Content-Type: application/json' \
-H 'X-Correlation-Id: <<auth.correlationId>>'
```

---

### 4. Get Products with Shopify Store Name (user-specific subdomain)
```bash
curl -X GET 'https://<<url.storeName>>.myshopify.com/admin/api/2025-07/products.json' \
-H 'Content-Type: application/json'
```

---

### 5. Static Endpoint with Query Parameters
```bash
curl -X GET 'https://api.stripe.com/v1/customers?limit=10' \
-H 'Content-Type: application/json'
```

---

### 6. Create with Static Endpoint and Body
```bash
curl -X POST 'https://api.openai.com/v1/completions' \
-H 'Content-Type: application/json' \
-d '{
  "model": "text-davinci-003",
  "prompt": "Hello world",
  "max_tokens": 100
}'
```

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


def fastn_function(params):
    """Function to extract API endpoints and cURL commands from a URL using Crawl4AI LLM strategy"""
    
    # Create Pydantic models without classes using create_model
    CurlCommand = create_model(
        'CurlCommand',
        name=(str, Field(description="Descriptive name for the API endpoint (e.g., 'listOrganizationMembers')")),
        curl=(str, Field(description="Complete cURL command with proper syntax using single quotes"))
    )
    
    CurlCommandList = create_model(
        'CurlCommandList', 
        commands=(List[CurlCommand], Field(description="List of extracted cURL commands"))
    )
    
    async def extract_with_crawl4ai(url: str) -> Dict:
        """Use Crawl4AI with LLM extraction strategy to get cURL commands"""
        
        # Concise system prompt with comprehensive mapping rules
        extraction_instruction = """You are performing LLM-based scraping of API documentation. Be extremely thorough and comprehensive.

**SCRAPING INSTRUCTIONS:**
- Read and understand ALL content fragments provided
- Extract EVERY endpoint, parameter, and detail mentioned
- Do NOT miss any APIs, methods, or functionality
- Look for information scattered across different sections
- Piece together incomplete information from multiple fragments
- Be exhaustive - capture everything the documentation offers

**CRITICAL MAPPING RULES:**
1. **BaseUrl Mapping**: Only map {host}, {domain}, {instance} placeholders to <<auth.baseUrl>> when URL varies per user. Keep static endpoints (api.github.com, api.openai.com) as-is.
2. **Path Parameters**: Map {userId}, {itemId}, {docId} → <<url.userId>>, <<url.itemId>>, <<url.docId>>
3. **Query Parameters**: Keep static (?page=1&limit=100) - do NOT template
4. **Bodies**: Static JSON only - no templating inside body
5. **Quotes**: Always use single quotes in cURL commands
6. **Headers**: Include ALL headers from documentation (Authorization, Content-Type, Accept, etc.)
7. **CAPTURE ALL PARAMETERS**: Include ALL query parameters and path parameters from documentation, even if marked as optional. Do not miss any parameters - include limit, offset, page, sort, order, filter, search, etc.

**COMPREHENSIVE EXAMPLE:**

Input Documentation:
```
Base URL: https://{domain}/api/v1
Authentication: Bearer token in Authorization header
Endpoints:
- GET /users/{userId}/items?page=1&limit=50&order=desc&search=query&filter=active (optional params: order, search, filter)
- POST /users/{userId}/items with body {"name": "item1", "active": true}
- DELETE /users/{userId}/items/{itemId}
```

Expected Output:
```json
[
  {
    "name": "getUserItems",
    "curl": "curl -X GET 'https://<<auth.baseUrl>>/api/v1/users/<<url.userId>>/items?page=1&limit=50&order=desc&search=query&filter=active' -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json' -H 'Accept: application/json'"
  },
  {
    "name": "createUserItem", 
    "curl": "curl -X POST 'https://<<auth.baseUrl>>/api/v1/users/<<url.userId>>/items' -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json' -d '{\"name\": \"item1\", \"active\": true}'"
  },
  {
    "name": "deleteUserItem",
    "curl": "curl -X DELETE 'https://<<auth.baseUrl>>/api/v1/users/<<url.userId>>/items/<<url.itemId>>' -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json'"
  }
]
```

**KEY MAPPINGS:**
- {domain}, {host}, {instance} → <<auth.baseUrl>>
- {userId}, {itemId}, {docId} → <<url.userId>>, <<url.itemId>>, <<url.docId>>
- Keep: ALL headers including Authorization, Content-Type, Accept
- Keep: Static query params, static JSON bodies
- IMPORTANT: Include ALL optional parameters (limit, page, order, search, filter, sort, offset, etc.) from documentation

Return [] if no endpoints found."""

        # Configure LLM extraction strategy
        llm_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4.1-nano",  # Using gpt-4o-mini  or gpt-4.1-nano as requested
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=CurlCommandList.model_json_schema(),
            extraction_type="schema",
            instruction=extraction_instruction,
            chunk_token_threshold=9000,
            overlap_rate=0.1,
            apply_chunking=True,
            input_format="markdown",  # Use markdown for better structure
            extra_args={"temperature": 0.1, "max_tokens": 9000}
        )

        # Build crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=llm_strategy,
            cache_mode=CacheMode.BYPASS
        )

        # Browser config
        browser_config = BrowserConfig(headless=True)

        try:
            print(f"🌐 Starting Crawl4AI extraction from: {url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawl_config)
                
                if result.success:
                    print("✅ Crawl4AI extraction successful")
                    
                    # Parse the extracted content
                    try:
                        extracted_data = json.loads(result.extracted_content)
                        
                        # Handle both list and dict structures
                        if isinstance(extracted_data, list):
                            commands = extracted_data
                        elif isinstance(extracted_data, dict):
                            commands = extracted_data.get('commands', [])
                        else:
                            print(f"⚠️ Unexpected data structure: {type(extracted_data)}")
                            commands = []
                        
                        # Commands are ready to use as-is
                        
                        print(f"🔗 Found {len(commands)} cURL commands")
                        llm_strategy.show_usage()  # Show token usage
                        
                        return {
                            "status": "success", 
                            "curl_commands": commands,
                            "count": len(commands)
                        }
                        
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON parse error: {e}")
                        print(f"Raw extracted content: {result.extracted_content[:500]}...")
                        return {
                            "status": "failed",
                            "error": f"Failed to parse extracted JSON: {str(e)}",
                            "curl_commands": [],
                            "count": 0
                        }
                else:
                    print(f"❌ Crawl4AI failed: {result.error_message}")
            return {
                "status": "failed",
                        "error": f"Crawl4AI extraction failed: {result.error_message}",
                "curl_commands": [],
                        "count": 0
                    }
                    
        except Exception as e:
            print(f"💥 Exception in Crawl4AI: {str(e)}")
            return {
                "status": "failed",
                "error": f"Exception during extraction: {str(e)}",
                "curl_commands": [],
                "count": 0
            }

    # Main function logic
    pageUrl = params['data']['input']['pageUrl']
    start_time = time.time()
    
    try:
        # Run the async extraction
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(extract_with_crawl4ai(pageUrl))
        loop.close()
            
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "curl_commands": [],
            "count": 0,
            "executionTime": "0 seconds"
        }
    
    # Calculate execution time and add to result
    duration = time.time() - start_time
    result["executionTime"] = f"{duration:.2f} seconds"
    
    # Return results
    return result

def main():
    """Test the fastn_function with GitBook API documentation"""
    
    # Test URL - GitBook Organization Members API documentation
    test_url = "https://gitbook.com/docs/developers/gitbook-api/api-reference/organizations/organization-members"
    
    # Structure params as expected by fastn_function
    test_params = {
        'data': {
            'input': {
                'pageUrl': test_url
            }
        }
    }
    
    print("🚀 Testing fastn_function with GitBook API documentation...")
    print(f"📄 URL: {test_url}")
    print("-" * 80)
    
    try:
        # Call the function
        result = fastn_function(test_params)
        
        # Display results
        print(f"\n✅ Status: {result['status']}")
        print(f"⏱️ Execution Time: {result['executionTime']}")
        print(f"🔗 Total Endpoints Found: {result['count']}")
        
        if result['status'] == 'success' and result['curl_commands']:
            print("\n📋 Extracted cURL Commands:")
            print("=" * 80)
            
            for i, curl_data in enumerate(result['curl_commands'], 1):
                print(f"\n{i}. {curl_data.get('name', 'Unnamed Endpoint')}")
                print(f"   cURL: {curl_data.get('curl', 'Not found')}")
                print("-" * 40)
        
        elif result['status'] == 'failed':
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n💥 Exception occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())



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
        "stage": "DRAFT",
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




if __name__ == "__main__":
    main()
