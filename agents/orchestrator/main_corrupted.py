"""
OrchestratorAgent - Main coordination agent and UI host
Port: 8010
Capabilities: agent coordination, service discovery, UI hosting, routing
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from f    async def route_chat_message(self, message: str, session_id: str = "default"):
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
        
        try:taticfiles import StaticFiles
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
            pricing_port = os.getenv("PRICING_AGENT_PORT", "8001")  # Updated to match current pricing service port
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
- **NEW:** Access complete transaction history and cost basis (use get_transaction_history function)
- **NEW:** Analyze position performance with P&L calculations (use analyze_position_performance function)
- **NEW:** Get detailed cost basis information (use get_cost_basis_info function)
- **NEW:** Market sentiment analysis with news intelligence (use analyze_market_sentiment function)
- **NEW:** Portfolio-wide sentiment overview (use get_portfolio_sentiment_overview function)
- **NEW:** News impact analysis on your holdings (use get_market_news_impact function)

**Transaction History Context:**
You have access to Milan Jugovic's complete trading history including:
- AAPL: 150 shares (bought in 2 transactions: Jan 15 & Mar 20, 2024)
- MSFT: 200 shares (bought in 2 transactions: Feb 10 & Apr 5, 2024)
- LLOY.L: 5000 shares (bought in 2 transactions: Jan 8 & Feb 28, 2024)
- SHEL: 800 shares (bought in 2 transactions: Mar 15 & May 12, 2024)
- TSLA: 80 shares (bought Apr 22, 2024)

**Function Calling Guidelines:**
- When users ask about stock prices, ALWAYS use get_stock_price or get_multiple_stock_prices
- When users ask about their transaction history, purchases, or "when did I buy", use get_transaction_history
- When users ask about performance, gains/losses, or P&L, use analyze_position_performance
- When users ask about cost basis or average cost, use get_cost_basis_info
- When users ask about market sentiment, news, or market conditions, use analyze_market_sentiment
- When users ask about overall portfolio sentiment or market outlook, use get_portfolio_sentiment_overview
- When users ask about news impact on their investments, use get_market_news_impact
- When users mention their holdings or ask about portfolio value, use analyze_portfolio_value
- When users ask about rebalancing or want trade recommendations, use create_rebalancing_plan
- For conceptual questions, use get_market_context or answer directly

**Handling Portfolio Data:**
When users provide holdings like "10 AMZN, 2 TSLA, 1 LLOY.L", convert to JSON format:
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
            
            # Configure Azure OpenAI
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if not azure_api_key or not azure_endpoint:
                logger.error("❌ Azure OpenAI credentials not found in environment")
                return
            
            # Add Azure OpenAI chat completion service
            self.chat_service = AzureChatCompletion(
                service_id="chat",
                deployment_name=azure_deployment,
                endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version
            )
            self.kernel.add_service(self.chat_service)
            logger.info(f"✅ Azure OpenAI configured: {azure_deployment}")
            print(f"✅ Using Azure OpenAI: {azure_endpoint} / {azure_deployment}", flush=True)
            
            # Add custom plugins
            stock_pricing_plugin = StockPricingPlugin(self.agents["pricing"])
            self.kernel.add_plugin(stock_pricing_plugin, plugin_name="StockPricing")
            logger.info("✅ StockPricing plugin registered")
            
            rebalancing_plugin = PortfolioRebalancingPlugin(self.agents["rebalance"])
            self.kernel.add_plugin(rebalancing_plugin, plugin_name="PortfolioRebalancing")
            logger.info("✅ PortfolioRebalancing plugin registered")
            
            market_insights_plugin = MarketInsightsPlugin()
            self.kernel.add_plugin(market_insights_plugin, plugin_name="MarketInsights")
            logger.info("✅ MarketInsights plugin registered")
            
            transaction_history_plugin = TransactionHistoryPlugin()
            self.kernel.add_plugin(transaction_history_plugin, plugin_name="TransactionHistory")
            logger.info("✅ TransactionHistory plugin registered")
            
            market_sentiment_plugin = MarketSentimentPlugin()
            self.kernel.add_plugin(market_sentiment_plugin, plugin_name="MarketSentiment")
            logger.info("✅ MarketSentiment plugin registered")
            
            print("🚀 Semantic Kernel fully initialized with auto function calling!", flush=True)
            logger.info("🚀 Semantic Kernel fully initialized with auto function calling!")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Semantic Kernel: {e}")
            import traceback
            traceback.print_exc()
            self.kernel = None
            self.chat_service = None
    
    async def discover_agents(self):
        """Discover available agents using A2A protocol"""
        discovered = {}
        
        for agent_name, base_url in self.agents.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Get agent card
                    response = await client.get(f"{base_url}/.well-known/agent-card")
                    if response.status_code == 200:
                        card = response.json()
                        
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
                    status="unavailable",
                    capabilities=[]
                )
        
        self.agent_info = discovered
        return discovered
    
    
    async def route_chat_message(self, message: str, session_id: str = "default"):
        """
        Route chat messages using Semantic Kernel with auto function calling.
        The AI will automatically decide when to call pricing or rebalancing functions.
        """
        print(f"� Processing message for session {session_id}: {message[:50]}...", flush=True)
        
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
            
            # Create execution settings for Azure OpenAI
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            
            execution_settings = AzureChatPromptExecutionSettings(
                service_id="chat",
                max_tokens=800,  # Reduced for faster responses
                temperature=0.3,  # Lower for faster, more focused responses
                top_p=0.9
            )
            
            
            print(f"🤖 Invoking AI with {len(self.kernel.plugins)} plugins available...", flush=True)
            
            # For SK 1.37, use get_chat_message_contents with execution settings
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
            
            settings = AzureChatPromptExecutionSettings(
                service_id="chat",
                max_tokens=800,  # Reduced for faster responses
                temperature=0.3,  # Lower for faster, more focused responses
                function_choice_behavior=FunctionChoiceBehavior.Auto()  # Enable auto function calling!
            )
            
            # Call the completion service with auto function calling
            response = await self.chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings,
                kernel=self.kernel
            )
            
            # Extract response text
            response_text = str(response[0].content) if response and len(response) > 0 else "No response generated."
            
            # Add assistant response to history
            chat_history.add_assistant_message(response_text)
            
            print(f"✅ AI response generated: {response_text[:100]}...", flush=True)
            
            return {
                "response": response_text,
                "session_id": session_id,
                "agent": "SK_OrchestratorAgent_AutoFunctions"
            }
                
        except Exception as e:
            print(f"❌ Error in route_chat_message: {e}", flush=True)
            import traceback
            traceback.print_exc()
            
            return {
                "response": f"💬 I'm experiencing technical difficulties. Error: {str(e)}",
                "session_id": session_id,
                "agent": "OrchestratorAgent"
            }
    
    async def route_rebalance_request(self, request_data):
        """Route rebalance request to RebalanceAgent"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.agents['rebalance']}/rebalance/plan",
                    json=request_data
                )
                return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RebalanceAgent error: {str(e)}")

# Initialize orchestrator service
orchestrator_service = OrchestratorService()

@app.on_event("startup")
async def startup_event():
    """Discover agents on startup"""
    await orchestrator_service.discover_agents()
    print("🚀 OrchestratorAgent started - Agent discovery complete")

@app.get("/")
def serve_ui():
    """Serve the main UI"""
    # Try container path first, then local development path
    for static_path in ["/app/static", "/Users/milanjugovic/a2a-milan/static"]:
        html_file = os.path.join(static_path, "index.html")
        if os.path.exists(html_file):
            return FileResponse(html_file)
    
    return {"error": "UI file not found", "checked_paths": ["/app/static/index.html", "/Users/milanjugovic/a2a-milan/static/index.html"]}

@app.get("/health")
def health():
    return {
        "agent": "OrchestratorAgent", 
        "status": "healthy", 
        "version": "1.0.0",
        "role": "coordinator"
    }

@app.get("/debug/sk")
def sk_debug():
    """Debug endpoint to check SK agent status"""
    return {
        "SK_AVAILABLE": SK_AVAILABLE,
        "sk_agent_initialized": orchestrator_service.sk_agent is not None,
        "chat_history_initialized": orchestrator_service.chat_history is not None,
    }

@app.get("/ui")
def ui_redirect():
    """Redirect to main UI"""
    return RedirectResponse(url="/static/index.html")

@app.get("/chat")
def chat_ui():
    """Redirect to main chat UI"""
    return RedirectResponse(url="/static/index.html")

@app.get("/.well-known/agent-card")
def agent_card():
    """A2A Agent Discovery Endpoint"""
    return JSONResponse(
        content={
            "name": "OrchestratorAgent",
            "version": "1.0.0",
            "description": "Main coordination agent and UI host for multi-agent wealth management system",
            "endpoints": {
                "chat": "/chat/message",
                "rebalance_plan": "/rebalance/plan", 
                "agents": "/agents",
                "discover": "/discover"
            },
            "capabilities": [
                "agent.coordination",
                "service.discovery", 
                "ui.hosting",
                "request.routing"
            ],
            "manages": ["PricingAgent", "RebalanceAgent", "ConversationalAgent"],
            "port": 8010,
            "streams": False,
            "auth": "none"
        }
    )

@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """Proxy price requests to PricingAgent"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{orchestrator_service.agents['pricing']}/price/{symbol}")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Price service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")

@app.get("/stream/prices")
async def stream_prices():
    """Server-Sent Events endpoint for real-time price updates"""
    async def generate_price_updates():
        symbols = ['AAPL', 'SHEL', 'LLOY.L', 'MSFT']
        while True:
            try:
                # Fetch all prices
                price_updates = {}
                pricing_url = orchestrator_service.agents.get('pricing', 'http://127.0.0.1:8011')
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for symbol in symbols:
                        try:
                            url = f"{pricing_url}/price/{symbol}"
                            response = await client.get(url)
                            if response.status_code == 200:
                                price_updates[symbol] = response.json()
                        except Exception as e:
                            print(f"SSE Error fetching {symbol}: {e}")
                            continue
                
                # Send the updates as SSE
                if price_updates:
                    import json
                    data = json.dumps(price_updates)
                    yield f"data: {data}\n\n"
                
                # Wait 10 seconds before next update
                await asyncio.sleep(10)
                
            except Exception as e:
                print(f"SSE error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(5)
    
    return StreamingResponse(
        generate_price_updates(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.post("/chat/message")
async def chat_message(chat: ChatMessage):
    """Proxy chat requests to ConversationalAgent"""
    return await orchestrator_service.route_chat_message(chat.message, chat.session_id)

@app.post("/rebalance/plan") 
async def rebalance_plan(request_data: dict):
    """Proxy rebalance requests to RebalanceAgent"""
    return await orchestrator_service.route_rebalance_request(request_data)

@app.get("/agents")
async def list_agents():
    """List all discovered agents"""
    agents = await orchestrator_service.discover_agents()
    return {
        "orchestrator": "OrchestratorAgent",
        "agents": agents,
        "total_agents": len(agents),
        "healthy_agents": len([a for a in agents.values() if a.status == "healthy"])
    }

@app.get("/discover")
async def rediscover_agents():
    """Manually trigger agent discovery"""
    agents = await orchestrator_service.discover_agents()
    return {
        "message": "Agent discovery completed",
        "discovered": agents,
        "timestamp": "now"
    }

@app.get("/health")
async def health_status():
    """Get comprehensive system health"""
    agents = await orchestrator_service.discover_agents()
    
    return {
        "agent": "OrchestratorAgent",
        "status": "healthy",
        "role": "coordinator",
        "capabilities": ["agent.coordination", "service.discovery", "ui.hosting"],
        "managed_agents": {
            name: {"status": info.status, "url": info.url} 
            for name, info in agents.items()
        },
        "system_health": {
            "total_agents": len(agents),
            "healthy_agents": len([a for a in agents.values() if a.status == "healthy"]),
            "ui_available": os.path.exists("/Users/milanjugovic/a2a-milan/static")
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ORCHESTRATOR_PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=port)
