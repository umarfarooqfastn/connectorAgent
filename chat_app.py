#!/usr/bin/env python3
"""
Clean Chat-based Connector Creation Agent
Uses OpenAI function tools for clean interaction
"""

import json
import os
import time
import sys
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import logging
import re

# Import existing components
from fastn_function import call_fastn_api, ORIGINAL_SYSTEM_PROMPT

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatConnectorAgent:
    def __init__(self, session_id=None):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create conversations directory
        self.conversations_dir = "conversations"
        os.makedirs(self.conversations_dir, exist_ok=True)
        
        self.conversation_file = os.path.join(self.conversations_dir, f"{self.session_id}.json")
        
        # Session data
        self.platform_name = None
        self.connector_group_id = None
        self.scraped_endpoints = []
        
        # Load existing conversation or start new
        self.conversation = self.load_conversation()
        
        logger.info(f"Started chat session: {self.session_id}")
    
    def save_conversation(self):
        """Save conversation to local JSON file"""
        try:
            conversation_data = {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "platform_name": self.platform_name,
                "connector_group_id": self.connector_group_id,
                "conversation": self.conversation
            }
            
            with open(self.conversation_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
    
    def load_conversation(self):
        """Load existing conversation from file"""
        try:
            if os.path.exists(self.conversation_file):
                with open(self.conversation_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Restore session data
                self.platform_name = data.get("platform_name")
                self.connector_group_id = data.get("connector_group_id")
                
                logger.info(f"Loaded existing conversation with {len(data.get('conversation', []))} messages")
                return data.get("conversation", [])
                
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
        
        return []
    
    def list_previous_sessions(self):
        """List all previous conversation sessions"""
        try:
            sessions = []
            for filename in os.listdir(self.conversations_dir):
                if filename.endswith('.json'):
                    session_id = filename[:-5]  # Remove .json
                    filepath = os.path.join(self.conversations_dir, filename)
                    
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            sessions.append({
                                "session_id": session_id,
                                "platform": data.get("platform_name", "Unknown"),
                                "created_at": data.get("created_at", "Unknown"),
                                "messages": len(data.get("conversation", []))
                            })
                    except:
                        continue
                        
            return sorted(sessions, key=lambda x: x["created_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "scrape_documentation",
                    "description": "Scrape API documentation to extract endpoints and auth info",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "platform_name": {"type": "string"}
                        },
                        "required": ["url", "platform_name"]
                    }
                }
            },
            {
          "type": "function",
          "function": {
            "name": "create_connector_endpoint_under_group",
            "description": "This function creates a connector endpoint using CURL commands. Curl Command Should be Valid should include required params headers , body. Verify it before calling this function.",
            "parameters": {
              "type": "object",
              "properties": {
                "name": { "type": "string", "description": "The name of the connector endpoint" },
                "curl": { "type": "string", "description": "The CURL command representing the connector's endpoint.Curl Command SHould be Valid should include required params headers , body. Verify it before calling this function. And Make sure varaiables are mapped correctly with <<name.prefix>>" },
                "connectorGroupId": { "type": "string", "description": "The ID of the connector group to add the connector to" }
              },
              "required": ["name", "curl", "connectorGroupId"]
            }
          }
        },
        {
          "type": "function",
          "function": {
            "name": "create_connector_group",
            "description": "Creates a new connector group with a specified authentication type and auth details dont miss any required.",
            "parameters": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "description": "The name for the new connector group."
                },
                "auth": {
                  "type": "object",
                  "description": "The authentication configuration for the group. The structure depends on the 'type' of authentication.",
                  "properties": {
                    "type": {
                      "type": "string",
                      "description": "The type of authentication.",
                      "enum": ["oauth", "basic", "apiKey", "bearerToken", "customInput", "none"]
                    },
                    "details": {
                      "type": "object",
                      "description": "A JSON object containing the specific configuration for the chosen auth type. For 'oauth', this includes 'baseUrl', 'clientId', etc. For 'basic', 'apiKey', 'bearerToken', or 'customInput', it would be the specific fields required by the platform."
                    }
                  },
                  "required": ["type", "details"]
                }
              },
              "required": ["name", "auth"]
            }
          }
        }
        ]
    
    def execute_tool(self, tool_name: str, arguments: dict):
        """Execute tool and return clean result"""
        
        if tool_name == "scrape_documentation":
            url = arguments["url"]
            platform_name = arguments["platform_name"]
            
            # Save session data
            self.platform_name = platform_name
            
            # Use fastn_function to extract endpoints
            params = {
                'data': {
                    'input': {
                        'pageUrl': url
                    }
                }
            }
            
            try:
                # Call fastn_function
                from fastn_function import fastn_function
                start_time = time.time()
                
                logger.info(f"🚀 Starting API extraction from URL: {url}")
                result = fastn_function(params)
                
                # Format extracted endpoints
                extracted_endpoints = []
                if result.get("curl_commands") and isinstance(result["curl_commands"], list):
                    for cmd in result["curl_commands"]:
                        if isinstance(cmd, dict) and "name" in cmd and "curl" in cmd:
                            endpoint = {
                                "name": cmd.get("name", ""),
                                "method": self._extract_method(cmd.get("curl", "")),
                                "url": self._extract_url(cmd.get("curl", "")),
                                "curl": cmd.get("curl", "")
                            }
                            extracted_endpoints.append(endpoint)
                
                self.scraped_endpoints = extracted_endpoints
                
                # Calculate execution time
                total_time = time.time() - start_time
                
                logger.info(f"✅ Found {len(extracted_endpoints)} endpoints in {total_time:.2f} seconds")
                
                # Build result
                api_result = {
                    "status": "success",
                    "pages_scraped": 1,
                    "endpoints_found": len(extracted_endpoints),
                    "extracted_endpoints": extracted_endpoints,
                    "execution_time": {
                        "total_seconds": round(total_time, 2),
                        "scraping_seconds": round(float(result.get("executionTime", "0 seconds").split()[0]), 2),
                        "extraction_seconds": round(total_time - float(result.get("executionTime", "0 seconds").split()[0]), 2)
                    }
                }
                
                return json.dumps(api_result)
                
            except Exception as e:
                logger.error(f"❌ Error using fastn_function: {str(e)}")
                error_result = {
                    "status": "failed",
                    "error": str(e),
                    "endpoints_found": 0,
                    "extracted_endpoints": []
                }
                return json.dumps(error_result)
            
        elif tool_name == "create_connector_group":
            result = call_fastn_api(tool_name, arguments)
            
            if "error" not in result:
                self.connector_group_id = result.get("connectorGroupId") or result.get("id")
                
            return json.dumps(result)
            
        elif tool_name == "create_connector_endpoint_under_group":
            # Use saved connector_group_id if not provided
            if not arguments.get("connectorGroupId") and self.connector_group_id:
                arguments["connectorGroupId"] = self.connector_group_id
                
            result = call_fastn_api(tool_name, arguments)
            return json.dumps(result)
        
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    def _extract_method(self, curl: str) -> str:
        if 'curl -X' in curl:
            parts = curl.split(' ')
            for i, part in enumerate(parts):
                if part == '-X' and i + 1 < len(parts):
                    return parts[i + 1]
        return 'GET'
    
    def _extract_url(self, curl: str) -> str:
        match = re.search(r'"(https?://[^"]*)"', curl)
        return match.group(1) if match else "unknown"
    
    def chat(self):
        print("🤖 " + "="*50)
        print("🤖 Fastn.ai Connector Creation Chat")
        print("🤖 Type 'quit' to exit")
        print("🤖 " + "="*50)
        
        # Initial message with full system prompt
        chat_workflow = """
CHAT WORKFLOW:
1. Ask user for platform name and documentation URL
2. Use scrape_documentation tool to analyze the API  
3. Based on scraping results, suggest authentication config
4. Use create_connector_group tool when user approves
5. Use create_connector_endpoint_under_group for each endpoint

TOOL USAGE:
- Always use tools to perform actions (no text commands)
- After scraping, analyze the results and suggest appropriate auth
- When creating endpoints, the connectorGroupId will be automatically used
- Be conversational and helpful
- Explain what you're doing at each step

"""

        self.conversation.append({
            "role": "system", 
            "content": chat_workflow + ORIGINAL_SYSTEM_PROMPT
        })
        
        print("\n🤖 Hi! I'll help you create Fastn.ai connectors.")
        print("🤖 What platform would you like to create a connector for?")
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    print("🤖 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Add user message
                self.conversation.append({"role": "user", "content": user_input})
                self.save_conversation()  # Save after user input
                
                # Get AI response with tools
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=self.conversation,
                    tools=self.get_tools(),
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=5000
                )
                
                message = response.choices[0].message
                
                # Handle tool calls
                if message.tool_calls:
                    # Add assistant message with tool calls
                    self.conversation.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in message.tool_calls
                        ]
                    })
                    
                    # Execute tools and add results
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        
                        print(f"🔧 Executing: {tool_name}")
                        result = self.execute_tool(tool_name, arguments)
                        
                        # Add tool result to conversation
                        self.conversation.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": result
                        })
                    
                    # Get AI's response to tool results
                    followup_response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=self.conversation,
                        tools=self.get_tools(),
                        tool_choice="none",  # Force text response after tool execution
                        temperature=0.7,
                        max_tokens=5000
                       
                    )
                    
                    followup_message = followup_response.choices[0].message
                    
                    # Always expect content after tool execution
                    if followup_message.content:
                        print(f"\n🤖 {followup_message.content}")
                        self.conversation.append({
                            "role": "assistant",
                            "content": followup_message.content
                        })
                    else:
                        # Fallback if still null - force a response
                        fallback_response = "Tool executed successfully. What would you like to do next?"
                        print(f"\n🤖 {fallback_response}")
                        self.conversation.append({
                            "role": "assistant",
                            "content": fallback_response
                        })
                    
                    self.save_conversation()  # Save after AI response
                    
                else:
                    # Regular text response
                    print(f"\n🤖 {message.content}")
                    self.conversation.append({
                        "role": "assistant", 
                        "content": message.content
                    })
                    self.save_conversation()  # Save after AI response
                
            except KeyboardInterrupt:
                print("\n🤖 Chat interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Chat error: {e}")
                print(f"🤖 Sorry, I encountered an error: {e}")

def main():
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            # List previous sessions
            agent = ChatConnectorAgent()
            sessions = agent.list_previous_sessions()
            
            if not sessions:
                print("No previous conversation sessions found.")
                return
                
            print("📋 Previous Conversation Sessions:")
            print("=" * 50)
            for i, session in enumerate(sessions[:10], 1):  # Show last 10
                print(f"{i}. {session['session_id']}")
                print(f"   Platform: {session['platform']}")
                print(f"   Messages: {session['messages']}")
                print(f"   Created: {session['created_at'][:19]}")
                print()
            
            if len(sessions) > 10:
                print(f"... and {len(sessions) - 10} more sessions")
            
            return
            
        elif sys.argv[1] == "--resume":
            if len(sys.argv) > 2:
                session_id = sys.argv[2]
                print(f"🔄 Resuming session: {session_id}")
                agent = ChatConnectorAgent(session_id=session_id)
            else:
                print("Usage: python chat_app.py --resume <session_id>")
                return
        else:
            print("Usage: python chat_app.py [--list | --resume <session_id>]")
            return
    else:
        # Start new session
        agent = ChatConnectorAgent()
    
    agent.chat()

if __name__ == "__main__":
    main()