"""
Semantic Kernel A2A RebalanceAgent
Uses Microsoft Semantic Kernel for portfolio optimization and agent communication
"""

import os
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Semantic Kernel imports
import semantic_kernel as sk
from semantic_kernel.functions import kernel_function
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import AzureChatPromptExecutionSettings
from semantic_kernel.contents.chat_history import ChatHistory
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="SK RebalanceAgent", description="Semantic Kernel A2A Portfolio Rebalancing Agent")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
class Position(BaseModel):
    symbol: str
    quantity: float
    avgCost: float

class Portfolio(BaseModel):
    baseCurrency: str = "USD"
    positions: List[Position]

class Constraints(BaseModel):
    maxTurnover: float = 0.2
    minTradeValue: float = 100.0

class RebalancePlanRequest(BaseModel):
    portfolio: Portfolio
    targets: Dict[str, float]
    constraints: Constraints

class Trade(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    estPrice: float
    reason: str

class RebalancePlanResponse(BaseModel):
    currentValue: float
    trades: List[Trade]
    notes: List[str]

class SKRebalanceAgent:
    def __init__(self):
        # Get pricing agent URL from environment
        agent_host = os.getenv("AGENT_HOST", "127.0.0.1")
        pricing_port = os.getenv("PRICING_AGENT_PORT", "8011")
        self.pricing_agent_url = f"http://{agent_host}:{pricing_port}"
        
        # Initialize Semantic Kernel
        self.kernel = sk.Kernel()
        self.chat_service = None
        self.setup_semantic_kernel()
        
    def setup_semantic_kernel(self):
        """Initialize Semantic Kernel with Azure OpenAI service"""
        try:
            # Azure OpenAI configuration
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if azure_api_key and azure_endpoint:
                self.chat_service = AzureChatCompletion(
                    service_id="chat",
                    deployment_name=azure_deployment,
                    endpoint=azure_endpoint,
                    api_key=azure_api_key,
                    api_version=azure_api_version
                )
                self.kernel.add_service(self.chat_service)
                print(f"✅ Azure OpenAI configured for RebalanceAgent: {azure_deployment}")
                print(f"🧠 SK AI reasoning enabled for portfolio analysis")
            else:
                print("⚠️ No Azure OpenAI credentials found. SK features limited.")
                
        except Exception as e:
            print(f"⚠️ SK setup warning: {e}")
    
    
    @kernel_function(
        name="calculate_portfolio_value",
        description="Calculate the total market value of a portfolio. Returns the current value with detailed breakdown by position."
    )
    async def sk_calculate_portfolio_value(self, portfolio_json: str) -> str:
        """SK function to calculate portfolio value with detailed breakdown"""
        try:
            portfolio_data = json.loads(portfolio_json)
            positions = portfolio_data.get('positions', [])
            
            # Get current prices
            symbols = [pos['symbol'] for pos in positions]
            prices = await self.get_current_prices(symbols)
            
            total_value = 0.0
            breakdown = []
            
            for pos in positions:
                symbol = pos['symbol']
                quantity = pos['quantity']
                current_price = prices.get(symbol, 100.0)
                position_value = quantity * current_price
                total_value += position_value
                
                breakdown.append(f"{symbol}: {quantity} shares @ ${current_price:.2f} = ${position_value:,.2f}")
            
            result = f"Portfolio Total Value: ${total_value:,.2f}\n\nBreakdown:\n" + "\n".join(breakdown)
            return result
            
        except Exception as e:
            return f"Error calculating portfolio value: {str(e)}"
    
    
    @kernel_function(
        name="analyze_portfolio_allocation",
        description="Analyze current portfolio allocation vs target allocation. Shows current weights, target weights, and differences."
    )
    async def sk_analyze_allocation(self, portfolio_json: str, targets_json: str) -> str:
        """SK function to analyze allocation differences"""
        try:
            portfolio_data = json.loads(portfolio_json)
            targets = json.loads(targets_json)
            positions = portfolio_data.get('positions', [])
            
            # Get current prices and calculate values
            symbols = [pos['symbol'] for pos in positions]
            prices = await self.get_current_prices(symbols)
            
            total_value = 0.0
            position_values = {}
            
            for pos in positions:
                symbol = pos['symbol']
                quantity = pos['quantity']
                current_price = prices.get(symbol, 100.0)
                value = quantity * current_price
                position_values[symbol] = value
                total_value += value
            
            # Calculate current weights
            analysis = ["Portfolio Allocation Analysis:", ""]
            analysis.append(f"Total Portfolio Value: ${total_value:,.2f}")
            analysis.append("")
            analysis.append("Current vs Target Allocation:")
            analysis.append("-" * 60)
            
            for symbol in sorted(set(list(position_values.keys()) + list(targets.keys()))):
                current_value = position_values.get(symbol, 0.0)
                current_weight = (current_value / total_value * 100) if total_value > 0 else 0.0
                target_weight = targets.get(symbol, 0.0) * 100
                difference = current_weight - target_weight
                
                status = "✅" if abs(difference) < 2 else "⚠️" if abs(difference) < 5 else "❌"
                analysis.append(f"{status} {symbol:6s} | Current: {current_weight:5.1f}% | Target: {target_weight:5.1f}% | Diff: {difference:+5.1f}%")
            
            return "\n".join(analysis)
            
        except Exception as e:
            return f"Error analyzing allocation: {str(e)}"
    
    @kernel_function(
        name="generate_rebalance_trades",
        description="Generate specific trades needed to rebalance a portfolio to target allocations within constraints. Returns detailed trade recommendations with reasoning."
    )
    async def sk_generate_trades(self, portfolio_json: str, targets_json: str, constraints_json: str) -> str:
        """SK function to generate rebalancing trades"""
        try:
            portfolio_data = json.loads(portfolio_json)
            targets = json.loads(targets_json)
            constraints = json.loads(constraints_json)
            
            # Get current prices
            symbols = [pos['symbol'] for pos in portfolio_data['positions']]
            prices = await self.get_current_prices(symbols)
            
            # Calculate current values and positions
            current_positions = {}
            total_value = 0.0
            
            for pos in portfolio_data['positions']:
                symbol = pos['symbol']
                quantity = pos['quantity']
                current_price = prices.get(symbol, 100.0)
                value = quantity * current_price
                
                current_positions[symbol] = {
                    'quantity': quantity,
                    'value': value,
                    'price': current_price
                }
                total_value += value
            
            # Generate trades
            trades = []
            notes = []
            max_turnover = constraints.get('maxTurnover', 0.2)
            min_trade_value = constraints.get('minTradeValue', 100.0)
            turnover_used = 0.0
            
            for target_symbol, target_weight in targets.items():
                target_value = total_value * target_weight
                current_value = current_positions.get(target_symbol, {}).get('value', 0.0)
                difference = target_value - current_value
                
                if abs(difference) > min_trade_value and turnover_used < max_turnover:
                    current_price = prices.get(target_symbol, 100.0)
                    quantity = abs(difference) / current_price
                    
                    trade = {
                        'symbol': target_symbol,
                        'side': 'BUY' if difference > 0 else 'SELL',
                        'quantity': round(quantity, 2),
                        'estPrice': current_price,
                        'reason': 'Rebalance to target allocation'
                    }
                    trades.append(trade)
                    
                    turnover_used += abs(difference) / total_value
                    
                    if turnover_used >= max_turnover:
                        notes.append("Turnover budget reached; some trades skipped.")
                        break
            
            result = {
                'currentValue': total_value,
                'trades': trades,
                'notes': notes
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error generating trades: {str(e)}"
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices from PricingAgent (try SK version first)"""
        try:
            # Try SK PricingAgent first
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.sk_pricing_agent_url}/prices", json=symbols)
                if response.status_code == 200:
                    data = response.json()
                    prices_data = data.get("prices", {})
                    # Handle both formats: {"AAPL": 256.33} or {"AAPL": {"price": 256.33, "currency": "USD"}}
                    result = {}
                    for symbol, value in prices_data.items():
                        if isinstance(value, dict):
                            result[symbol] = value.get("price", 100.0)
                        else:
                            result[symbol] = value
                    return result
        except:
            pass
            
        try:
            # Fallback to original PricingAgent
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.pricing_agent_url}/prices", json=symbols)
                if response.status_code == 200:
                    data = response.json()
                    prices_data = data.get("prices", {})
                    # Handle both formats
                    result = {}
                    for symbol, value in prices_data.items():
                        if isinstance(value, dict):
                            result[symbol] = value.get("price", 100.0)
                        else:
                            result[symbol] = value
                    return result
        except:
            pass
        
        # Final fallback
        return {symbol: 100.0 for symbol in symbols}
    
    async def generate_rebalance_plan_with_ai(self, request: RebalancePlanRequest) -> dict:
        """Generate portfolio rebalancing plan using SK AI reasoning"""
        if not self.chat_service:
            raise ValueError("Semantic Kernel chat service not initialized")
        
        # Prepare data as JSON strings for SK functions
        portfolio_json = json.dumps({
            "positions": [
                {"symbol": pos.symbol, "quantity": pos.quantity}
                for pos in request.portfolio.positions
            ]
        })
        
        targets_json = json.dumps(request.targets)
        constraints_json = json.dumps({
            "maxTurnover": request.constraints.maxTurnover,
            "minTradeValue": request.constraints.minTradeValue
        })
        
        # Create a prompt for the AI to analyze the portfolio
        system_prompt = """You are a professional portfolio manager. You have access to functions that can:
1. Calculate total portfolio value with breakdown by position
2. Analyze current allocation vs target allocation
3. Generate specific trades to rebalance the portfolio

Provide clear, well-structured recommendations in HTML format with proper formatting."""

        user_prompt = f"""Analyze this portfolio and provide a rebalancing plan in clean HTML format:

Portfolio: {portfolio_json}
Target Allocation: {targets_json}
Constraints: {constraints_json}

Use the available functions, then format your response as HTML with:
- <h3> for section headers
- <ul> and <li> for lists
- <strong> for emphasis on numbers and actions
- <p> for paragraphs
- Use emojis: 📊 for data, ⚖️ for balance, 💰 for money, 🎯 for targets, ⚠️ for warnings, ✅ for good
- Keep it concise and actionable

Include these sections:
1. Current Portfolio Summary
2. Allocation Analysis (current vs target)
3. Recommended Trades
4. Rationale"""

        # Use SK with auto function calling to generate insights
        settings = AzureChatPromptExecutionSettings(
            temperature=0.3,  # Lower temperature for more consistent financial advice
            max_tokens=2000,
            function_choice_behavior=FunctionChoiceBehavior.Auto()
        )
        
        # Create chat history for this request
        history = ChatHistory()
        history.add_system_message(system_prompt)
        history.add_user_message(user_prompt)
        
        # Get AI response with auto function calling
        try:
            response = await self.chat_service.get_chat_message_contents(
                chat_history=history,
                settings=settings,
                kernel=self.kernel
            )
            
            ai_analysis = str(response[0])
            
            # Clean up the response - remove markdown code blocks if present
            if ai_analysis.startswith("```html"):
                ai_analysis = ai_analysis[7:]  # Remove ```html
            if ai_analysis.endswith("```"):
                ai_analysis = ai_analysis[:-3]  # Remove ```
            ai_analysis = ai_analysis.strip()
            
            # Remove <!DOCTYPE> and <html> tags for embedding
            import re
            # Extract just the body content for embedding
            body_match = re.search(r'<body>(.*?)</body>', ai_analysis, re.DOTALL)
            if body_match:
                ai_analysis = body_match.group(1).strip()
            
            return {
                "success": True,
                "ai_analysis": ai_analysis,
                "function_calls_made": len(response[0].items) if hasattr(response[0], 'items') else 0
            }
            
        except Exception as e:
            logger.error(f"SK AI analysis error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "ai_analysis": "AI analysis failed - falling back to traditional method"
            }
    
    async def generate_rebalance_plan(self, request: RebalancePlanRequest) -> RebalancePlanResponse:
        """Generate portfolio rebalancing plan using SK reasoning"""
        portfolio = request.portfolio
        targets = request.targets
        constraints = request.constraints
        
        # Get current market prices
        symbols = [pos.symbol for pos in portfolio.positions]
        prices = await self.get_current_prices(symbols)
        
        # Calculate current portfolio state
        current_positions = {}
        total_value = 0.0
        
        for position in portfolio.positions:
            current_price = prices.get(position.symbol, 100.0)
            position_value = position.quantity * current_price
            
            current_positions[position.symbol] = {
                'quantity': position.quantity,
                'value': position_value,
                'price': current_price,
                'weight': 0.0  # Will calculate after total
            }
            total_value += position_value
        
        # Calculate current weights
        for symbol in current_positions:
            current_positions[symbol]['weight'] = current_positions[symbol]['value'] / total_value
        
        # Generate trades to reach target allocation
        trades = []
        notes = []
        turnover_used = 0.0
        
        for target_symbol, target_weight in targets.items():
            target_value = total_value * target_weight
            current_value = current_positions.get(target_symbol, {}).get('value', 0.0)
            difference = target_value - current_value
            
            # Only trade if difference is significant and within turnover budget
            if abs(difference) > constraints.minTradeValue and turnover_used < constraints.maxTurnover:
                current_price = prices.get(target_symbol, 100.0)
                quantity_needed = abs(difference) / current_price
                
                trade = Trade(
                    symbol=target_symbol,
                    side="BUY" if difference > 0 else "SELL",
                    quantity=round(quantity_needed, 2),
                    estPrice=current_price,
                    reason="Reduce overweight" if difference < 0 else "Increase underweight"
                )
                trades.append(trade)
                
                # Track turnover usage
                turnover_used += abs(difference) / total_value
                
                if turnover_used >= constraints.maxTurnover:
                    notes.append("Turnover budget reached; some trades skipped.")
                    break
        
        if len(trades) == 0:
            notes.append("Portfolio is already well-balanced within constraints.")
        
        return RebalancePlanResponse(
            currentValue=total_value,
            trades=trades,
            notes=notes
        )

# Initialize the SK RebalanceAgent
rebalance_agent = SKRebalanceAgent()

# Add SK functions to kernel
rebalance_agent.kernel.add_function(
    plugin_name="rebalance",
    function=rebalance_agent.sk_calculate_portfolio_value
)
rebalance_agent.kernel.add_function(
    plugin_name="rebalance",
    function=rebalance_agent.sk_analyze_allocation
)
rebalance_agent.kernel.add_function(
    plugin_name="rebalance",
    function=rebalance_agent.sk_generate_trades
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "agent": "SK_RebalanceAgent", 
        "status": "healthy",
        "semantic_kernel": "enabled",
        "sk_functions": len(rebalance_agent.kernel.plugins.get("rebalance", {}).functions) if rebalance_agent.kernel.plugins.get("rebalance") else 0,
        "capabilities": [
            "portfolio.analysis",
            "portfolio.rebalancing", 
            "trade.generation",
            "semantic.kernel.powered"
        ],
        "dependencies": {
            "PricingAgent": rebalance_agent.pricing_agent_url
        }
    }

@app.get("/.well-known/agent-card")
async def agent_card():
    """Semantic Kernel A2A Agent Discovery Endpoint"""
    return {
        "name": "SK_RebalanceAgent",
        "version": "1.0.0", 
        "description": "Semantic Kernel powered agent for portfolio optimization and rebalancing",
        "semantic_kernel": {
            "enabled": True,
            "functions": ["calculate_portfolio_value", "generate_rebalance_trades"],
            "plugins": ["rebalance"]
        },
        "endpoints": {
            "rebalance_plan": "/rebalance/plan",
            "rebalance_plan_ai": "/rebalance/plan/ai",
            "health": "/health", 
            "sk_chat": "/sk/chat"
        },
        "capabilities": [
            "portfolio.analysis",
            "portfolio.rebalancing",
            "trade.generation",
            "semantic.kernel.powered",
            "ai.reasoning"
        ],
        "port": 8012,
        "streams": False,
        "auth": "none",
        "framework": "semantic_kernel"
    }

@app.post("/rebalance/plan")
async def rebalance_plan(request: RebalancePlanRequest):
    """Generate portfolio rebalancing plan"""
    try:
        plan = await rebalance_agent.generate_rebalance_plan(request)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rebalance/plan/ai")
async def rebalance_plan_ai(request: RebalancePlanRequest):
    """Generate portfolio rebalancing plan with AI-powered analysis and natural language explanations"""
    try:
        result = await rebalance_agent.generate_rebalance_plan_with_ai(request)
        
        # Also get the traditional plan for structured data
        traditional_plan = await rebalance_agent.generate_rebalance_plan(request)
        
        return {
            "ai_powered": True,
            "ai_analysis": result.get("ai_analysis", ""),
            "function_calls_made": result.get("function_calls_made", 0),
            "traditional_plan": {
                "currentValue": traditional_plan.currentValue,
                "trades": [trade.dict() for trade in traditional_plan.trades],
                "notes": traditional_plan.notes
            },
            "success": result.get("success", False)
        }
    except Exception as e:
        logger.error(f"AI rebalancing endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sk/chat")
async def sk_chat_endpoint(message: dict):
    """Semantic Kernel powered chat for portfolio advice"""
    try:
        user_message = message.get("message", "")
        
        response = f"""I'm the Semantic Kernel RebalanceAgent! I can help you with:

📊 Portfolio Analysis & Rebalancing
⚖️ Trade Generation with Constraints  
🎯 Target Allocation Planning
🤖 AI-Powered Investment Reasoning

You asked: "{user_message}"

For portfolio rebalancing, use the /rebalance/plan endpoint with your portfolio data."""
        
        return {
            "response": response,
            "agent": "SK_RebalanceAgent",
            "capabilities": ["portfolio.rebalancing", "semantic.kernel.powered"],
            "session_id": message.get("session_id", "default")
        }
        
    except Exception as e:
        return {
            "response": f"Error processing request: {str(e)}",
            "agent": "SK_RebalanceAgent",
            "error": True
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("REBALANCE_AGENT_PORT", "8012"))
    print(f"🚀 Starting Semantic Kernel RebalanceAgent on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
