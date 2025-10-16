"""
Semantic Kernel Plugins for Orchestrator Agent
Provides AI-accessible functions for stock pricing and portfolio rebalancing
"""
import httpx
import json
from typing import Dict, Optional
from semantic_kernel.functions import kernel_function


class StockPricingPlugin:
    """Plugin for real-time stock pricing operations"""
    
    def __init__(self, pricing_agent_url: str):
        self.pricing_agent_url = pricing_agent_url
    
    @kernel_function(
        name="get_stock_price",
        description="Get the current real-time price of a stock with currency symbol. Use this when user asks about stock prices, quotes, or current trading values."
    )
    async def get_stock_price(self, symbol: str) -> str:
        """
        Get real-time stock price with currency.
        
        Args:
            symbol: Stock ticker symbol (e.g., AAPL, MSFT, LLOY.L for London stocks)
        
        Returns:
            A formatted string with the current price and currency
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.pricing_agent_url}/price/{symbol.upper()}")
                
                if response.status_code == 200:
                    data = response.json()
                    currency = data.get('currency', '$')
                    price = data['price']
                    stock_symbol = data['symbol']
                    source = data.get('source', 'Yahoo Finance')
                    
                    return f"📈 **{stock_symbol}** is currently trading at **{currency}{price:.2f}** (Source: {source})"
                else:
                    return f"❌ Unable to get price for {symbol}. The symbol may be invalid or the service is unavailable."
                    
        except Exception as e:
            return f"❌ Error retrieving price for {symbol}: {str(e)}"
    
    @kernel_function(
        name="get_multiple_stock_prices",
        description="Get current prices for multiple stocks at once. Use this when user asks about several stocks in one query."
    )
    async def get_multiple_prices(self, symbols: str) -> str:
        """
        Get prices for multiple stocks.
        
        Args:
            symbols: Comma-separated list of stock symbols (e.g., "AAPL,MSFT,GOOGL")
        
        Returns:
            A formatted string with all prices
        """
        try:
            symbol_list = [s.strip().upper() for s in symbols.split(',')]
            results = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for symbol in symbol_list:
                    try:
                        response = await client.get(f"{self.pricing_agent_url}/price/{symbol}")
                        if response.status_code == 200:
                            data = response.json()
                            currency = data.get('currency', '$')
                            price = data['price']
                            results.append(f"**{data['symbol']}**: {currency}{price:.2f}")
                        else:
                            results.append(f"**{symbol}**: ❌ Not available")
                    except:
                        results.append(f"**{symbol}**: ❌ Error")
            
            if results:
                return "📊 **Stock Prices:**\n" + "\n".join(results)
            else:
                return "❌ Unable to retrieve any stock prices."
                
        except Exception as e:
            return f"❌ Error retrieving multiple prices: {str(e)}"


class PortfolioRebalancingPlugin:
    """Plugin for portfolio analysis and rebalancing operations"""
    
    def __init__(self, rebalance_agent_url: str):
        self.rebalance_agent_url = rebalance_agent_url
    
    @kernel_function(
        name="create_rebalancing_plan",
        description="""Create a portfolio rebalancing plan with specific trades. Use this when user wants to 'rebalance' their portfolio.
        
        IMPORTANT: You must extract portfolio holdings from the conversation history. If user previously mentioned holdings like "10 AMZN, 5 AAPL, 3 MSFT", convert to JSON format.
        
        If user provides target allocation like "25/25/25/25" or "AMZN: 25%, AAPL: 25%", create equal weights for all stocks.
        
        Example: User says "10 AMZN, 5 AAPL" and "25/25" for targets
        - portfolio_json: [{"symbol": "AMZN", "quantity": 10, "avgCost": 100}, {"symbol": "AAPL", "quantity": 5, "avgCost": 150}]
        - targets_json: {"AMZN": 0.25, "AAPL": 0.25}"""
    )
    async def create_rebalancing_plan(
        self, 
        portfolio_json: str, 
        targets_json: str,
        max_turnover: str = "0.2",
        min_trade_value: str = "100.0"
    ) -> str:
        """
        Generate a rebalancing plan with specific trade recommendations.
        
        Args:
            portfolio_json: JSON string with portfolio positions [{"symbol": "AAPL", "quantity": 10, "avgCost": 150}]
            targets_json: JSON string with target allocations {"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3}
            max_turnover: Maximum portfolio turnover allowed (default: 0.2 = 20%)
            min_trade_value: Minimum trade value in dollars (default: 100.0)
        
        Returns:
            A detailed rebalancing plan with trades and analysis
        """
        try:
            # Parse inputs
            import json
            positions = json.loads(portfolio_json)
            targets = json.loads(targets_json)
            
            # Build request
            request_data = {
                "portfolio": {
                    "baseCurrency": "USD",
                    "positions": positions
                },
                "targets": targets,
                "constraints": {
                    "maxTurnover": float(max_turnover),
                    "minTradeValue": float(min_trade_value)
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use the AI-powered endpoint for clean HTML output
                response = await client.post(
                    f"{self.rebalance_agent_url}/rebalance/plan/ai",
                    json=request_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Return the AI-generated HTML analysis
                    if result.get('success') and result.get('ai_analysis'):
                        return result['ai_analysis']
                    else:
                        # Fallback to traditional format if AI fails
                        plan = result.get('traditional_plan', {})
                        output = f"⚖️ **Portfolio Rebalancing Plan**\n\n"
                        output += f"💼 **Current Portfolio Value**: ${plan.get('currentValue', 0):,.2f}\n\n"
                        
                        if plan.get('trades'):
                            output += "📋 **Recommended Trades:**\n"
                            for i, trade in enumerate(plan['trades'], 1):
                                side_emoji = "🟢" if trade['side'] == 'BUY' else "🔴"
                                output += f"{i}. {side_emoji} **{trade['side']}** {trade['quantity']} shares of **{trade['symbol']}** @ ~${trade['estPrice']:.2f}\n"
                                output += f"   _{trade['reason']}_\n"
                        else:
                            output += "✅ **No trades needed** - Portfolio is already well-balanced!\n"
                        
                        if plan.get('notes'):
                            output += f"\n📝 **Notes:**\n"
                            for note in plan['notes']:
                                output += f"• {note}\n"
                        
                        return output
                else:
                    return f"❌ Rebalancing service returned an error: {response.status_code}"
                    
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON format: {str(e)}. Please provide valid JSON for portfolio and targets."
        except Exception as e:
            return f"❌ Error creating rebalancing plan: {str(e)}"
    
    @kernel_function(
        name="analyze_portfolio_value",
        description="Analyze a user's portfolio - calculates total value, shows allocation breakdown, and provides insights. Use this when user mentions their holdings (e.g., '10 AMZN, 5 AAPL') or asks about portfolio performance, value, or analysis. Accepts simple format like 'symbol: quantity'."
    )
    async def analyze_portfolio_value(self, portfolio_json: str) -> str:
        """
        Calculate total portfolio value with detailed analysis and HTML formatting.
        
        Args:
            portfolio_json: JSON string with positions [{"symbol": "AAPL", "quantity": 10, "avgCost": 150}]
                          Can also parse from natural language like "10 AMZN, 5 AAPL"
        
        Returns:
            Current portfolio value and breakdown
        """
        try:
            import json
            positions = json.loads(portfolio_json)
            
            request_data = {
                "portfolio": {
                    "baseCurrency": "USD",
                    "positions": positions
                },
                "targets": {pos['symbol']: 1.0/len(positions) for pos in positions},  # Equal weight dummy
                "constraints": {"maxTurnover": 0.0, "minTradeValue": 999999.0}  # No trades
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use the AI-powered endpoint for better analysis
                response = await client.post(
                    f"{self.rebalance_agent_url}/rebalance/plan/ai",
                    json=request_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Return the AI-generated HTML analysis  
                    if result.get('success') and result.get('ai_analysis'):
                        return result['ai_analysis']
                    else:
                        # Fallback to simple value
                        plan = result.get('traditional_plan', {})
                        return f"💼 **Total Portfolio Value**: ${plan.get('currentValue', 0):,.2f}"
                else:
                    return f"❌ Unable to calculate portfolio value"
                    
        except Exception as e:
            return f"❌ Error analyzing portfolio: {str(e)}"


class MarketInsightsPlugin:
    """Plugin for general market insights and information"""
    
    @kernel_function(
        name="get_market_context",
        description="Get general information about markets, trading, or investment concepts. Use this for educational questions."
    )
    async def get_market_context(self, topic: str) -> str:
        """
        Provide market context and educational information.
        
        Args:
            topic: The market topic or concept to explain
        
        Returns:
            Educational information about the topic
        """
        # This is a placeholder - in production, you might connect to a knowledge base
        context_map = {
            "diversification": "📚 **Diversification** is the practice of spreading investments across different assets to reduce risk. The idea is that different assets perform differently under various market conditions.",
            "rebalancing": "📚 **Rebalancing** is adjusting your portfolio back to target allocations. As some investments grow faster than others, your portfolio can drift from its intended allocation.",
            "turnover": "📚 **Portfolio Turnover** measures how much of a portfolio's holdings change over a period. High turnover can mean higher transaction costs and taxes.",
            "allocation": "📚 **Asset Allocation** is how you divide investments among different asset categories like stocks, bonds, and cash. It's a key factor in portfolio performance.",
        }
        
        topic_lower = topic.lower()
        for key, value in context_map.items():
            if key in topic_lower:
                return value
        
        return f"📚 I can provide information about market concepts like diversification, rebalancing, turnover, and allocation. Ask me about a specific topic!"


class MarketSentimentPlugin:
    """Plugin for AI-powered market sentiment analysis and news intelligence"""
    
    def __init__(self):
        # Simulated sentiment data - in production, this would connect to news APIs
        self.sentiment_data = {
            "AAPL": {
                "sentiment_score": 0.75,  # -1 to 1 scale
                "news_summary": "Strong Q4 earnings beat expectations, iPhone 16 sales robust, AI chip partnerships expanding",
                "recent_events": ["Q4 earnings beat", "New AI partnerships", "Strong iPhone sales"],
                "market_buzz": "Bullish",
                "confidence": 0.85
            },
            "MSFT": {
                "sentiment_score": 0.68,
                "news_summary": "Azure growth continues, AI integration driving enterprise adoption, cloud market share gains",
                "recent_events": ["Azure growth acceleration", "AI Copilot adoption", "Enterprise deals"],
                "market_buzz": "Positive",
                "confidence": 0.82
            },
            "TSLA": {
                "sentiment_score": 0.45,
                "news_summary": "Mixed signals on FSD progress, energy business growth, production scaling challenges",
                "recent_events": ["FSD beta updates", "Energy storage growth", "Production targets"],
                "market_buzz": "Cautiously Optimistic",
                "confidence": 0.65
            },
            "SHEL": {
                "sentiment_score": 0.32,
                "news_summary": "Oil price volatility concerns, renewable transition investments, geopolitical tensions",
                "recent_events": ["Oil price fluctuations", "Renewable investments", "Geopolitical risks"],
                "market_buzz": "Mixed",
                "confidence": 0.70
            },
            "LLOY.L": {
                "sentiment_score": 0.28,
                "news_summary": "UK economic uncertainty, interest rate impacts, banking sector challenges",
                "recent_events": ["UK economic data", "Interest rate changes", "Banking regulations"],
                "market_buzz": "Cautious",
                "confidence": 0.75
            }
        }
    
    @kernel_function(
        name="analyze_market_sentiment",
        description="Get AI-powered market sentiment analysis for a stock with news insights and market mood. Use when users ask about market sentiment, news impact, or current market conditions."
    )
    async def analyze_market_sentiment(self, symbol: str) -> str:
        """
        Analyze market sentiment and news impact for intelligent investment decisions.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            Comprehensive sentiment analysis with actionable insights
        """
        try:
            symbol = symbol.upper()
            if symbol not in self.sentiment_data:
                return f"❌ Sentiment analysis not available for {symbol}. Available: {', '.join(self.sentiment_data.keys())}"
            
            data = self.sentiment_data[symbol]
            sentiment_score = data["sentiment_score"]
            
            # Determine sentiment emoji and description
            if sentiment_score >= 0.6:
                sentiment_emoji = "🟢"
                sentiment_desc = "Bullish"
                color = "positive"
            elif sentiment_score >= 0.3:
                sentiment_emoji = "🟡"
                sentiment_desc = "Neutral"
                color = "cautious"
            else:
                sentiment_emoji = "🔴"
                sentiment_desc = "Bearish"
                color = "negative"
            
            # Format confidence level
            confidence_stars = "⭐" * int(data["confidence"] * 5)
            
            result = f"📰 **Market Sentiment Analysis for {symbol}**\n\n"
            result += f"**Sentiment Score**: {sentiment_emoji} {sentiment_score:.2f}/1.00 ({sentiment_desc})\n"
            result += f"**Market Buzz**: {data['market_buzz']}\n"
            result += f"**Confidence**: {confidence_stars} ({data['confidence']:.1%})\n\n"
            
            result += f"📊 **News Summary**:\n{data['news_summary']}\n\n"
            
            result += f"📈 **Recent Market Events**:\n"
            for event in data["recent_events"]:
                result += f"• {event}\n"
            
            # Add AI-powered investment insight
            result += f"\n🤖 **AI Investment Insight**:\n"
            if sentiment_score >= 0.6:
                result += f"Strong positive sentiment suggests potential upward momentum. Consider this favorable environment for your {symbol} position."
            elif sentiment_score >= 0.3:
                result += f"Mixed sentiment indicates market uncertainty. Monitor closely and consider your risk tolerance for {symbol}."
            else:
                result += f"Negative sentiment suggests caution. Review your {symbol} position and consider defensive strategies."
            
            return result
            
        except Exception as e:
            return f"❌ Error analyzing sentiment for {symbol}: {str(e)}"
    
    @kernel_function(
        name="get_portfolio_sentiment_overview",
        description="Get overall sentiment analysis for the entire portfolio. Use when users ask about overall market conditions or portfolio-wide sentiment."
    )
    async def get_portfolio_sentiment_overview(self) -> str:
        """
        Get comprehensive sentiment analysis for the entire portfolio.
        
        Returns:
            Portfolio-wide sentiment summary with risk assessment
        """
        try:
            result = "📊 **Portfolio Sentiment Overview**\n\n"
            
            total_sentiment = 0
            sentiment_details = []
            
            for symbol, data in self.sentiment_data.items():
                sentiment_score = data["sentiment_score"]
                total_sentiment += sentiment_score
                
                if sentiment_score >= 0.6:
                    emoji = "🟢"
                elif sentiment_score >= 0.3:
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                
                sentiment_details.append(f"{emoji} **{symbol}**: {sentiment_score:.2f} ({data['market_buzz']})")
            
            # Calculate average sentiment
            avg_sentiment = total_sentiment / len(self.sentiment_data)
            
            # Overall portfolio sentiment
            if avg_sentiment >= 0.6:
                overall_emoji = "🟢"
                overall_desc = "Bullish"
                risk_level = "Low"
            elif avg_sentiment >= 0.4:
                overall_emoji = "🟡"
                overall_desc = "Neutral"
                risk_level = "Moderate"
            else:
                overall_emoji = "🔴"
                overall_desc = "Cautious"
                risk_level = "Elevated"
            
            result += f"**Overall Portfolio Sentiment**: {overall_emoji} {avg_sentiment:.2f}/1.00 ({overall_desc})\n"
            result += f"**Risk Level**: {risk_level}\n\n"
            
            result += "**Individual Holdings Sentiment**:\n"
            for detail in sentiment_details:
                result += f"{detail}\n"
            
            result += f"\n🎯 **Portfolio Strategy Recommendation**:\n"
            if avg_sentiment >= 0.5:
                result += "Positive sentiment across holdings suggests growth opportunities. Consider maintaining current allocations."
            elif avg_sentiment >= 0.3:
                result += "Mixed sentiment suggests selective approach. Focus on highest conviction positions."
            else:
                result += "Cautious sentiment suggests defensive positioning. Consider reducing risk exposure."
            
            return result
            
        except Exception as e:
            return f"❌ Error analyzing portfolio sentiment: {str(e)}"
    
    @kernel_function(
        name="get_market_news_impact",
        description="Analyze how current market news might impact your specific holdings. Use when users ask about news impact or market events affecting their investments."
    )
    async def get_market_news_impact(self, symbol: str = "ALL") -> str:
        """
        Analyze news impact on specific holdings or entire portfolio.
        
        Args:
            symbol: Stock ticker symbol or 'ALL' for portfolio-wide analysis
        
        Returns:
            News impact analysis with actionable recommendations
        """
        try:
            if symbol.upper() == "ALL":
                result = "📰 **Market News Impact Analysis - Full Portfolio**\n\n"
                
                high_impact = []
                medium_impact = []
                low_impact = []
                
                for stock_symbol, data in self.sentiment_data.items():
                    sentiment = data["sentiment_score"]
                    if sentiment >= 0.6 or sentiment <= 0.2:
                        high_impact.append(f"{stock_symbol}: {data['market_buzz']}")
                    elif sentiment >= 0.4:
                        medium_impact.append(f"{stock_symbol}: {data['market_buzz']}")
                    else:
                        low_impact.append(f"{stock_symbol}: {data['market_buzz']}")
                
                if high_impact:
                    result += "🔥 **High Impact Holdings**:\n"
                    for item in high_impact:
                        result += f"• {item}\n"
                    result += "\n"
                
                if medium_impact:
                    result += "⚡ **Medium Impact Holdings**:\n"
                    for item in medium_impact:
                        result += f"• {item}\n"
                    result += "\n"
                
                if low_impact:
                    result += "📊 **Stable Holdings**:\n"
                    for item in low_impact:
                        result += f"• {item}\n"
                
                result += "\n💡 **Action Items**: Monitor high-impact holdings closely for trading opportunities."
                
                return result
            else:
                return await self.analyze_market_sentiment(symbol)
                
        except Exception as e:
            return f"❌ Error analyzing news impact: {str(e)}"


class TransactionHistoryPlugin:
    """Plugin for managing and analyzing transaction history with contextual intelligence"""
    
    def __init__(self):
        # In-memory transaction data - realistic trading history
        self.transaction_data = {
            "AAPL": [
                {"date": "2024-01-15", "action": "BUY", "shares": 50, "price": 185.50, "total": 9275.00},
                {"date": "2024-03-20", "action": "BUY", "shares": 100, "price": 225.30, "total": 22530.00},
            ],
            "MSFT": [
                {"date": "2024-02-10", "action": "BUY", "shares": 75, "price": 405.50, "total": 30412.50},
                {"date": "2024-04-05", "action": "BUY", "shares": 125, "price": 435.80, "total": 54475.00},
            ],
            "LLOY.L": [
                {"date": "2024-01-08", "action": "BUY", "shares": 2500, "price": 0.8420, "total": 2105.00},
                {"date": "2024-02-28", "action": "BUY", "shares": 2500, "price": 0.8908, "total": 2227.00},
            ],
            "SHEL": [
                {"date": "2024-03-15", "action": "BUY", "shares": 400, "price": 68.75, "total": 27500.00},
                {"date": "2024-05-12", "action": "BUY", "shares": 400, "price": 74.42, "total": 29768.00},
            ],
            "TSLA": [
                {"date": "2024-04-22", "action": "BUY", "shares": 80, "price": 162.50, "total": 13000.00},
            ]
        }
    
    @kernel_function(
        name="get_transaction_history",
        description="Get complete transaction history for a stock symbol or all holdings. Use this when users ask about their purchase history, when they bought stocks, or trading patterns."
    )
    async def get_transaction_history(self, symbol: str = "ALL") -> str:
        """
        Get transaction history for analysis and contextual recommendations.
        
        Args:
            symbol: Stock ticker symbol or 'ALL' for complete history
        
        Returns:
            Formatted transaction history with analysis
        """
        try:
            if symbol.upper() == "ALL":
                result = "📊 **Complete Transaction History**\n\n"
                total_invested = 0
                
                for stock_symbol, transactions in self.transaction_data.items():
                    result += f"**{stock_symbol}:**\n"
                    stock_total = 0
                    total_shares = 0
                    
                    for tx in transactions:
                        currency = "£" if stock_symbol == "LLOY.L" else "$"
                        result += f"• {tx['date']}: {tx['action']} {tx['shares']} shares @ {currency}{tx['price']:.2f} = {currency}{tx['total']:,.2f}\n"
                        stock_total += tx['total']
                        if tx['action'] == 'BUY':
                            total_shares += tx['shares']
                    
                    avg_cost = stock_total / total_shares if total_shares > 0 else 0
                    currency = "£" if stock_symbol == "LLOY.L" else "$"
                    result += f"  *Total: {total_shares} shares, Avg Cost: {currency}{avg_cost:.2f}, Invested: {currency}{stock_total:,.2f}*\n\n"
                    
                    if stock_symbol != "LLOY.L":  # Convert to USD for total
                        total_invested += stock_total
                    else:  # Convert GBP to USD (approximate)
                        total_invested += stock_total * 1.27
                
                result += f"💰 **Portfolio Total Invested: ${total_invested:,.2f}**"
                return result
                
            else:
                symbol = symbol.upper()
                if symbol not in self.transaction_data:
                    return f"❌ No transaction history found for {symbol}. Available symbols: {', '.join(self.transaction_data.keys())}"
                
                transactions = self.transaction_data[symbol]
                result = f"📊 **Transaction History for {symbol}**\n\n"
                
                total_shares = 0
                total_invested = 0
                currency = "£" if symbol == "LLOY.L" else "$"
                
                for tx in transactions:
                    result += f"• **{tx['date']}**: {tx['action']} {tx['shares']} shares @ {currency}{tx['price']:.2f} = {currency}{tx['total']:,.2f}\n"
                    total_invested += tx['total']
                    if tx['action'] == 'BUY':
                        total_shares += tx['shares']
                
                avg_cost = total_invested / total_shares if total_shares > 0 else 0
                result += f"\n📈 **Summary**: {total_shares} total shares, Average cost: {currency}{avg_cost:.2f}, Total invested: {currency}{total_invested:,.2f}"
                
                return result
                
        except Exception as e:
            return f"❌ Error retrieving transaction history: {str(e)}"
    
    @kernel_function(
        name="analyze_position_performance",
        description="Analyze a stock position's performance including cost basis, current value, and P&L. Use when users ask about their performance, gains/losses, or investment returns."
    )
    async def analyze_position_performance(self, symbol: str, current_price: Optional[float] = None) -> str:
        """
        Analyze position performance with transaction context.
        
        Args:
            symbol: Stock ticker symbol
            current_price: Optional current price (will fetch if not provided)
        
Returns:
            Detailed performance analysis with recommendations
        """
        try:
            symbol = symbol.upper()
            if symbol not in self.transaction_data:
                return f"❌ No transaction history found for {symbol}"
            
            transactions = self.transaction_data[symbol]
            total_shares = sum(tx['shares'] for tx in transactions if tx['action'] == 'BUY')
            total_invested = sum(tx['total'] for tx in transactions if tx['action'] == 'BUY')
            avg_cost = total_invested / total_shares if total_shares > 0 else 0
            
            currency = "£" if symbol == "LLOY.L" else "$"
            
            # If no current price provided, we'll work with what we have
            if current_price:
                current_value = current_price * total_shares
                unrealized_pnl = current_value - total_invested
                pnl_percent = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0
                
                pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
                pnl_color = "🟢" if unrealized_pnl >= 0 else "🔴"
                
                result = f"📊 **{symbol} Position Analysis**\n\n"
                result += f"• **Shares Owned**: {total_shares:,}\n"
                result += f"• **Average Cost**: {currency}{avg_cost:.2f}\n"
                result += f"• **Total Invested**: {currency}{total_invested:,.2f}\n"
                result += f"• **Current Price**: {currency}{current_price:.2f}\n"
                result += f"• **Current Value**: {currency}{current_value:,.2f}\n"
                result += f"• **Unrealized P&L**: {pnl_color} {currency}{abs(unrealized_pnl):,.2f} ({pnl_percent:+.1f}%) {pnl_emoji}\n\n"
                
                # Add contextual advice
                if unrealized_pnl > 0:
                    result += f"💡 **Insight**: Strong performance! Consider taking some profits or holding for long-term growth."
                else:
                    result += f"💡 **Insight**: Position is underwater. Consider dollar-cost averaging if you believe in long-term prospects."
            else:
                result = f"📊 **{symbol} Position Summary**\n\n"
                result += f"• **Shares Owned**: {total_shares:,}\n"
                result += f"• **Average Cost**: {currency}{avg_cost:.2f}\n"
                result += f"• **Total Invested**: {currency}{total_invested:,.2f}\n"
                result += f"• **Purchase History**: {len(transactions)} transactions\n"
                
            return result
            
        except Exception as e:
            return f"❌ Error analyzing position: {str(e)}"
    
    @kernel_function(
        name="get_cost_basis_info",
        description="Get detailed cost basis information for portfolio holdings. Use when users ask about their average cost, cost basis, or want to know their purchase prices."
    )
    async def get_cost_basis_info(self, symbol: str = "ALL") -> str:
        """
        Get cost basis information for informed trading decisions.
        
        Args:
            symbol: Stock ticker symbol or 'ALL' for all positions
        
        Returns:
            Cost basis summary with trading insights
        """
        try:
            if symbol.upper() == "ALL":
                result = "💰 **Portfolio Cost Basis Summary**\n\n"
                
                for stock_symbol in self.transaction_data.keys():
                    transactions = self.transaction_data[stock_symbol]
                    total_shares = sum(tx['shares'] for tx in transactions if tx['action'] == 'BUY')
                    total_invested = sum(tx['total'] for tx in transactions if tx['action'] == 'BUY')
                    avg_cost = total_invested / total_shares if total_shares > 0 else 0
                    currency = "£" if stock_symbol == "LLOY.L" else "$"
                    
                    result += f"**{stock_symbol}**: {total_shares:,} shares @ {currency}{avg_cost:.2f} avg cost\n"
                
                return result
            else:
                symbol = symbol.upper()
                if symbol not in self.transaction_data:
                    return f"❌ No cost basis data for {symbol}"
                
                transactions = self.transaction_data[symbol]
                total_shares = sum(tx['shares'] for tx in transactions if tx['action'] == 'BUY')
                total_invested = sum(tx['total'] for tx in transactions if tx['action'] == 'BUY')
                avg_cost = total_invested / total_shares if total_shares > 0 else 0
                currency = "£" if symbol == "LLOY.L" else "$"
                
                result = f"💰 **{symbol} Cost Basis**\n\n"
                result += f"• **Average Cost**: {currency}{avg_cost:.2f}\n"
                result += f"• **Total Shares**: {total_shares:,}\n"
                result += f"• **Total Investment**: {currency}{total_invested:,.2f}\n"
                
                return result
                
        except Exception as e:
            return f"❌ Error retrieving cost basis: {str(e)}"
