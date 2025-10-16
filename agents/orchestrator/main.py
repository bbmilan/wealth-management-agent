"""
OrchestratorAgent - Main coordination agent and UI host
Port: 8010
Capabilities: agent coordination, service discovery, UI hosting, routing
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import httpx
import asyncio
import os

# Semantic Kernel imports
try:
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
    from semantic_kernel.contents.chat_history import ChatHistory
    SK_AVAILABLE = True
    print("✅ Semantic Kernel successfully imported!")
except ImportError as e:
    SK_AVAILABLE = False
    print(f"❌ Semantic Kernel not available: {e}")

# Import our custom plugins
try:
    from agents.orchestrator.plugins import (
        StockPricingPlugin,
        PortfolioRebalancingPlugin,
        MarketInsightsPlugin,
        TransactionHistoryPlugin,
        MarketSentimentPlugin
    )
    PLUGINS_AVAILABLE = True
except ImportError as e:
    PLUGINS_AVAILABLE = False
    print(f"⚠️ Custom plugins not available: {e}")

app = FastAPI(title="OrchestratorAgent", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = "/app/static"
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
else:
    # Fallback for local development
    local_static_path = "/Users/milanjugovic/a2a-milan/static"
    if os.path.exists(local_static_path):
        app.mount("/static", StaticFiles(directory=local_static_path), name="static")

# Data Models
class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"

class AgentInfo(BaseModel):
    name: str
    url: str
    status: str
    capabilities: List[str]

class OrchestratorService:
    def __init__(self):
        # Get agent URLs from environment (use full URLs from Azure Container Apps)
        pricing_url = os.getenv("PRICING_AGENT_URL")
        rebalance_url = os.getenv("REBALANCE_AGENT_URL")
        
        # Fallback to local URLs if environment variables not set
        if not pricing_url:
            pricing_port = os.getenv("PRICING_AGENT_PORT", "8011")  # Updated to match current pricing service port
            agent_host = os.getenv("AGENT_HOST", "127.0.0.1")
            pricing_url = f"http://{agent_host}:{pricing_port}"
            
        if not rebalance_url:
            rebalance_port = os.getenv("REBALANCE_AGENT_PORT", "8012")
            agent_host = os.getenv("AGENT_HOST", "127.0.0.1")
            rebalance_url = f"http://{agent_host}:{rebalance_port}"
        
        self.agents = {
            "pricing": pricing_url,
            "rebalance": rebalance_url
        }
        self.agent_info = {}
        
        # Per-session chat histories (CRITICAL: Don't share history between users!)
        self.chat_histories = {}
        
        # Simple response cache for performance optimization
        self.response_cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        
        # Semantic Kernel setup
        self.kernel = None
        self.chat_service = None
        
        # Initialize Semantic Kernel with plugins if available
        if SK_AVAILABLE and PLUGINS_AVAILABLE:
            self._initialize_semantic_kernel()
    
    def get_or_create_chat_history(self, session_id: str):
        """Get or create a chat history for a specific session"""
        if session_id not in self.chat_histories:
            chat_history = ChatHistory()
            
            # Add system message with instructions
            chat_history.add_system_message("""You are an AI-powered Financial Advisor and Portfolio Management Assistant with access to comprehensive transaction history.

**Your Enhanced Capabilities:**
- Get real-time stock prices for any publicly traded company (use get_stock_price function)
- Analyze multiple stocks simultaneously (use get_multiple_stock_prices function)
- Create detailed portfolio rebalancing plans with specific trades (use create_rebalancing_plan function)
- Calculate portfolio values and provide detailed analysis (use analyze_portfolio_value function)
- Provide market insights and explain financial concepts (use get_market_context function)
- Analyze market sentiment for stocks (use analyze_market_sentiment function)
- Access transaction history for specific symbols (use get_transaction_history function)

**Built-in Portfolio Data:**
You have access to realistic transaction history:
- AAPL: 2 purchases (75 shares @ $225.50, 75 shares @ $235.80) = 150 shares
- MSFT: 2 purchases (75 shares @ $405.50, 125 shares @ $435.80) = 200 shares  
- LLOY.L: 3 purchases (500 shares @ £0.85, 1000 shares @ £0.82, 1000 shares @ £0.88) = 2500 shares
- SHEL: 2 purchases (50 shares @ $68.50, 75 shares @ $71.20) = 125 shares
- TSLA: 2 purchases (25 shares @ $240.00, 25 shares @ $255.50) = 50 shares

**For Portfolio Value Calculations:**
When user asks "analyze my portfolio" or mentions specific holdings, use analyze_portfolio_value with JSON format:
[{"symbol": "AAPL", "quantity": 150, "avgCost": 230.65}, {"symbol": "MSFT", "quantity": 200, "avgCost": 424.44}]
For user-specified holdings like "10 AMZN, 5 AAPL", use avgCost: 100 as placeholder:
[{"symbol": "AMZN", "quantity": 10, "avgCost": 100}, {"symbol": "TSLA", "quantity": 2, "avgCost": 100}, {"symbol": "LLOY.L", "quantity": 1, "avgCost": 100}]
Then call analyze_portfolio_value with this JSON.

**Handling Rebalancing Requests:**
When user asks to "rebalance my portfolio":
1. LOOK BACK in the conversation history to find their holdings (e.g., "10 AMZN, 5 AAPL, 3 MSFT")
2. Ask for target allocations if not provided (e.g., "Do you want equal weights?")
3. When user says "25/25/25/25" or "equal weights", create targets JSON: {"AMZN": 0.25, "AAPL": 0.25, "MSFT": 0.25, "LLOY.L": 0.25}
4. Call create_rebalancing_plan with:
   - portfolio_json: Convert holdings to JSON (use avgCost: 100 as placeholder)
   - targets_json: Equal weights or user-specified weights
   - max_turnover: "0.2" (allow 20% portfolio turnover)
   - min_trade_value: "100.0" (minimum $100 per trade)

Example:
User history shows: "10 AMZN, 5 AAPL, 3 MSFT, 1 LLOY.L"
User says: "Rebalance with equal weights"
You should call: create_rebalancing_plan(
  portfolio_json='[{"symbol":"AMZN","quantity":10,"avgCost":100},{"symbol":"AAPL","quantity":5,"avgCost":100},{"symbol":"MSFT","quantity":3,"avgCost":100},{"symbol":"LLOY.L","quantity":1,"avgCost":100}]',
  targets_json='{"AMZN":0.25,"AAPL":0.25,"MSFT":0.25,"LLOY.L":0.25}',
  max_turnover="0.2",
  min_trade_value="100.0"
)

**Response Style:**
- Professional yet conversational tone
- Use financial emojis (📈, 💼, ⚖️, 📊, 💰) to make responses engaging
- When functions return HTML (like analyze_portfolio_value), return it directly - do NOT add extra text
- Always cite data sources when providing real-time information

**Important:** You have access to real-time market data and AI-powered portfolio analysis. Use your functions proactively!""")
            
            self.chat_histories[session_id] = chat_history
            print(f"✅ Created new chat history for session: {session_id}", flush=True)
            
        return self.chat_histories[session_id]
    
    
    def _initialize_semantic_kernel(self):
        """Initialize Semantic Kernel with Azure OpenAI and plugins"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            # Create kernel
            self.kernel = sk.Kernel()
            logger.info("Kernel created")
            
            # Get Azure OpenAI configuration
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
            
            if not endpoint or not api_key:
                print("❌ Azure OpenAI configuration missing. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY")
                return
            
            print(f"🔑 Azure OpenAI Endpoint: {endpoint}")
            print(f"🚀 Deployment: {deployment}")
            
            # Add Azure OpenAI chat completion service
            self.chat_service = AzureChatCompletion(
                service_id="chat",
                deployment_name=deployment,
                endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            self.kernel.add_service(self.chat_service)
            
            print("✅ Azure OpenAI service added to kernel")
            
            # Add our custom plugins to the kernel
            if PLUGINS_AVAILABLE:
                # Add stock pricing plugin
                pricing_plugin = StockPricingPlugin(self.agents["pricing"])
                self.kernel.add_plugin(pricing_plugin, plugin_name="StockPricingPlugin")
                print("✅ StockPricingPlugin added")
                
                # Add portfolio rebalancing plugin
                rebalancing_plugin = PortfolioRebalancingPlugin(self.agents["rebalance"])
                self.kernel.add_plugin(rebalancing_plugin, plugin_name="PortfolioRebalancingPlugin")
                print("✅ PortfolioRebalancingPlugin added")
                
                # Add market insights plugin
                insights_plugin = MarketInsightsPlugin(self.agents["pricing"])
                self.kernel.add_plugin(insights_plugin, plugin_name="MarketInsightsPlugin")
                print("✅ MarketInsightsPlugin added")
                
                # Add transaction history plugin
                history_plugin = TransactionHistoryPlugin()
                self.kernel.add_plugin(history_plugin, plugin_name="TransactionHistoryPlugin")
                print("✅ TransactionHistoryPlugin added")
                
                # Add market sentiment plugin
                sentiment_plugin = MarketSentimentPlugin()
                self.kernel.add_plugin(sentiment_plugin, plugin_name="MarketSentimentPlugin")
                print("✅ MarketSentimentPlugin added")
                
                print(f"🎯 Total plugins loaded: {len(self.kernel.plugins)}")
            
        except Exception as e:
            print(f"❌ Failed to initialize Semantic Kernel: {e}")
            import traceback
            traceback.print_exc()
    
    async def route_chat_message(self, message: str, session_id: str = "default"):
        """
        Route chat messages using Semantic Kernel with auto function calling.
        The AI will automatically decide when to call pricing or rebalancing functions.
        """
        print(f"🔄 Processing message for session {session_id}: {message[:50]}...", flush=True)
        
        # Check cache for quick responses (for simple price queries)
        import hashlib
        import time
        
        cache_key = hashlib.md5(f"{message.lower().strip()}".encode()).hexdigest()
        current_time = time.time()
        
        if cache_key in self.response_cache:
            cached_response, cached_time = self.response_cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                print(f"⚡ Cache hit for message: {message[:30]}...", flush=True)
                cached_response["session_id"] = session_id  # Update session ID
                return cached_response
        
        try:
            # Check if SK is available
            if self.kernel is None or self.chat_service is None:
                return {
                    "response": "🤖 AI service is not available. Please check configuration.",
                    "session_id": session_id,
                    "agent": "OrchestratorAgent"
                }
            
            # Get or create chat history for this session
            chat_history = self.get_or_create_chat_history(session_id)
            
            # Add user message to history
            chat_history.add_user_message(message)
            print(f"✅ Added message to session {session_id} history (total messages: {len(chat_history.messages)})", flush=True)
            
            # Create execution settings for Azure OpenAI with performance optimizations
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            
            execution_settings = AzureChatPromptExecutionSettings(
                service_id="chat",
                max_tokens=400,  # Further reduced for 10 TPM quota
                temperature=0.1,  # Very low for fastest responses
                top_p=0.8
            )
            
            
            print(f"🤖 Invoking AI with {len(self.kernel.plugins)} plugins available...", flush=True)
            
            # For SK 1.37, use get_chat_message_contents with execution settings
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
            
            settings = AzureChatPromptExecutionSettings(
                service_id="chat",
                max_tokens=400,  # Further reduced for 10 TPM quota
                temperature=0.1,  # Very low for fastest responses
                function_choice_behavior=FunctionChoiceBehavior.Auto()  # Enable auto function calling!
            )
            
            # Call the completion service with auto function calling
            response = await self.chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings,
                kernel=self.kernel
            )
            
            # Get the response text
            if response and len(response) > 0:
                response_text = str(response[0])
                
                # Add assistant response to chat history
                chat_history.add_assistant_message(response_text)
                
                print(f"✅ AI response generated: {response_text[:50]}...", flush=True)
                
                result = {
                    "response": response_text,
                    "session_id": session_id,
                    "agent": "SK_OrchestratorAgent_AutoFunctions"
                }
                
                # Cache the response for performance (only simple queries)
                if len(message) < 100:  # Only cache short queries
                    self.response_cache[cache_key] = (result, current_time)
                
                return result
            else:
                return {
                    "response": "🤖 I apologize, but I couldn't generate a response. Please try again.",
                    "session_id": session_id,
                    "agent": "SK_OrchestratorAgent_AutoFunctions"
                }
                
        except Exception as e:
            print(f"❌ Error in AI processing: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "response": f"🤖 I encountered an error: {str(e)}. Please try again.",
                "session_id": session_id,
                "agent": "OrchestratorAgent_Error"
            }

    async def get_agent_health(self, agent_name: str) -> dict:
        """Check health status of an agent"""
        if agent_name not in self.agents:
            return {"status": "unknown", "agent": agent_name}
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.agents[agent_name]}/health")
                return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e), "agent": agent_name}

    async def get_stock_price_direct(self, symbol: str) -> dict:
        """Direct stock price lookup"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.agents['pricing']}/price/{symbol}")
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Failed to get price for {symbol}", "status_code": response.status_code}
        except Exception as e:
            return {"error": str(e)}

    async def get_streaming_prices(self, symbols: List[str]):
        """Stream price updates for multiple symbols"""
        async def generate():
            while True:
                for symbol in symbols:
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.get(f"{self.agents['pricing']}/price/{symbol}")
                            if response.status_code == 200:
                                data = response.json()
                                yield f"data: {response.text}\n\n"
                    except Exception as e:
                        error_data = {"symbol": symbol, "error": str(e)}
                        yield f"data: {error_data}\n\n"
                    
                    await asyncio.sleep(2)  # 2 second delay between symbols
                
                await asyncio.sleep(10)  # 10 second delay before next round
        
        return generate()

    async def discover_agents(self) -> Dict[str, AgentInfo]:
        """Discover available agents and their capabilities"""
        discovered = {}
        
        for agent_name, base_url in self.agents.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Get agent card
                    card_response = await client.get(f"{base_url}/.well-known/agent-card")
                    if card_response.status_code == 200:
                        card = card_response.json()
                    else:
                        card = {}
                    
                    # Check health
                    health_response = await client.get(f"{base_url}/health")
                    health_status = "healthy" if health_response.status_code == 200 else "unhealthy"
                    
                    discovered[agent_name] = AgentInfo(
                        name=card.get("name", agent_name),
                        url=base_url,
                        status=health_status,
                        capabilities=card.get("capabilities", [])
                    )
            except Exception as e:
                discovered[agent_name] = AgentInfo(
                    name=agent_name,
                    url=base_url,
                    status="error",
                    capabilities=[]
                )
        
        self.agent_info = discovered
        return discovered


# Initialize the orchestrator service
orchestrator_service = OrchestratorService()

# FastAPI Routes

@app.get("/")
async def root():
    """Redirect to the UI"""
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"agent": "OrchestratorAgent", "status": "healthy", "version": "1.0.0", "role": "coordinator"}

@app.get("/debug/sk")
async def debug_semantic_kernel():
    """Debug endpoint for Semantic Kernel status"""
    return {
        "semantic_kernel_available": SK_AVAILABLE,
        "plugins_available": PLUGINS_AVAILABLE,
        "kernel_initialized": orchestrator_service.kernel is not None,
        "plugins_loaded": len(orchestrator_service.kernel.plugins) if orchestrator_service.kernel else 0
    }

@app.get("/ui")
async def get_ui():
    """Serve the main UI"""
    return RedirectResponse(url="/static/index.html")

@app.get("/chat")
async def chat_interface():
    """Chat interface endpoint"""
    return {"message": "Chat interface available at /chat/message"}

@app.get("/.well-known/agent-card")
async def agent_card():
    """Agent discovery card"""
    return {
        "name": "OrchestratorAgent",
        "description": "AI-powered portfolio management orchestrator with Semantic Kernel",
        "version": "1.0.0",
        "capabilities": [
            "agent_coordination",
            "ui_hosting", 
            "chat_interface",
            "semantic_kernel_ai",
            "portfolio_analysis",
            "stock_pricing",
            "market_sentiment"
        ],
        "endpoints": {
            "health": "/health",
            "chat": "/chat/message",
            "ui": "/static/index.html",
            "agents": "/agents",
            "discover": "/discover"
        }
    }

@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """Get stock price for a symbol"""
    return await orchestrator_service.get_stock_price_direct(symbol)

@app.get("/stream/prices")
async def stream_prices(symbols: str = "AAPL,MSFT,LLOY.L,SHEL,TSLA"):
    """Stream real-time price updates"""
    symbol_list = [s.strip() for s in symbols.split(",")]
    generator = await orchestrator_service.get_streaming_prices(symbol_list)
    return StreamingResponse(generator, media_type="text/event-stream")

@app.post("/chat/message")
async def chat_message(chat: ChatMessage):
    """Process chat messages with AI"""
    return await orchestrator_service.route_chat_message(chat.message, chat.session_id)

@app.post("/rebalance/plan") 
async def create_rebalance_plan():
    """Create portfolio rebalancing plan"""
    return {"message": "Use /chat/message for AI-powered rebalancing"}

@app.get("/agents")
async def list_agents():
    """List all available agents and their status"""
    agents_info = {}
    for name, url in orchestrator_service.agents.items():
        health = await orchestrator_service.get_agent_health(name)
        agents_info[name] = {
            "url": url,
            "health": health
        }
    return agents_info

@app.get("/discover")
async def discover_agents():
    """Discover agent capabilities"""
    return await orchestrator_service.discover_agents()

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "semantic_kernel": SK_AVAILABLE,
        "plugins": PLUGINS_AVAILABLE
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ORCHESTRATOR_PORT", "8010"))
    print(f"🚀 Starting OrchestratorAgent on port {port}")
    print(f"📊 UI available at: http://localhost:{port}/static/index.html")
    uvicorn.run(app, host="0.0.0.0", port=port)