"""
PricingAgent - Specialized agent for market data and stock pricing
Port: 8011
Capabilities: stock pricing, market data, Yahoo Finance integration (real-time)
"""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import Dict, List
import yfinance as yf
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = FastAPI(title="PricingAgent", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PricingService:
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_ttl = 60  # 1 minute cache for more frequent real-time updates
        self.request_count = 0
        self.last_request_time = 0
        self.min_request_interval = 2.0  # Start with 2 seconds (more reasonable)
        self.max_request_interval = 15.0  # Cap at 15 seconds max
        self.consecutive_failures = 0  # Track consecutive failures for backoff
        self.success_count = 0  # Track successful requests
        self.success_count = 0  # Track successful requests
        
        # Setup requests session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # Exponential backoff: 1, 2, 4 seconds
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # More realistic fallback prices (updated October 2024)
        self._fallback_prices = {
            "AAPL": 225.0,    # Apple realistic price
            "MSFT": 420.0,    # Microsoft realistic price  
            "TSLA": 240.0,    # Tesla realistic price
            "AMZN": 186.0,    # Amazon realistic price (October 2024)
            "SHEL": 68.5,     # Shell realistic price
            "LLOY.L": 0.85,   # Lloyds realistic price
            "GOOGL": 165.0,   # Google realistic price
            "NVDA": 875.0,    # NVIDIA realistic price
        }
    
    def get_currency_symbol(self, symbol: str, ticker_info: dict) -> str:
        """Determine currency symbol based on stock exchange"""
        # Try to get currency from ticker info first
        if 'currency' in ticker_info:
            currency = ticker_info['currency'].upper()
            currency_map = {
                'USD': '$',
                'GBP': '£',
                'EUR': '€',
                'GBX': 'p',  # British pence
            }
            if currency in currency_map:
                return currency_map[currency]
        
        # Fallback: determine by symbol suffix
        if '.L' in symbol:  # London Stock Exchange
            return '£'
        elif '.PA' in symbol or '.DE' in symbol or '.MI' in symbol:  # Paris, Frankfurt, Milan
            return '€'
        else:  # Default to USD for US stocks
            return '$'

    def _rate_limit_request(self):
        """Smart rate limiting that adapts based on success/failure rate"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Calculate effective interval based on recent success/failure pattern
        if self.consecutive_failures > 0:
            # Exponential backoff for failures, but more moderate
            backoff_multiplier = min(1.5 ** self.consecutive_failures, 5.0)
            effective_interval = self.min_request_interval * backoff_multiplier
        else:
            # Use base interval when successful
            effective_interval = self.min_request_interval
            
        effective_interval = min(effective_interval, self.max_request_interval)
        
        if time_since_last < effective_interval:
            sleep_time = effective_interval - time_since_last
            print(f"⏱️ Rate limiting: sleeping for {sleep_time:.2f} seconds (failures: {self.consecutive_failures})")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1

    async def get_price_from_yahoo_direct(self, symbol: str) -> dict:
        """Try multiple Yahoo Finance endpoints with different strategies"""
        
        # Strategy 1: Try the chart API (most reliable)
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            print(f"📡 Chart API response for {symbol}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                chart = data.get('chart', {})
                if 'result' in chart and chart['result'] and len(chart['result']) > 0:
                    result = chart['result'][0]
                    meta = result.get('meta', {})
                    
                    # Get the latest price
                    price = meta.get('regularMarketPrice') or meta.get('previousClose')
                    if price and price > 0:
                        currency = self.get_currency_symbol(symbol, meta)
                        previous_close = meta.get('previousClose', price)
                        change = price - previous_close
                        change_percent = (change / previous_close * 100) if previous_close != 0 else 0.0
                        
                        print(f"✅ Chart API success for {symbol}: ${price}")
                        return {
                            "symbol": symbol,
                            "price": round(price, 2),
                            "currency": currency,
                            "change": round(change, 2),
                            "change_percent": round(change_percent, 2),
                            "day_high": meta.get('regularMarketDayHigh', price),
                            "day_low": meta.get('regularMarketDayLow', price),
                            "previous_close": previous_close,
                            "pre_market_price": meta.get('preMarketPrice'),
                            "pre_market_change": meta.get('preMarketChange'),
                            "pre_market_change_percent": None,
                            "is_market_open": meta.get('marketState') == 'REGULAR',
                            "last_updated": "Real-time via Chart API"
                        }
        except Exception as e:
            print(f"⚠️ Chart API failed for {symbol}: {e}")
        
        # Strategy 2: Try the quote API as fallback
        try:
            url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            print(f"📡 Quote API response for {symbol}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                quote_response = data.get('quoteResponse', {})
                if 'result' in quote_response and quote_response['result']:
                    quote = quote_response['result'][0]
                    
                    price = quote.get('regularMarketPrice')
                    if price and price > 0:
                        currency = self.get_currency_symbol(symbol, quote)
                        previous_close = quote.get('regularMarketPreviousClose', price)
                        change = quote.get('regularMarketChange', 0)
                        change_percent = quote.get('regularMarketChangePercent', 0)
                        
                        print(f"✅ Quote API success for {symbol}: ${price}")
                        return {
                            "symbol": symbol,
                            "price": round(price, 2),
                            "currency": currency,
                            "change": round(change, 2),
                            "change_percent": round(change_percent, 2),
                            "day_high": quote.get('regularMarketDayHigh', price),
                            "day_low": quote.get('regularMarketDayLow', price),
                            "previous_close": previous_close,
                            "pre_market_price": quote.get('preMarketPrice'),
                            "pre_market_change": quote.get('preMarketChange'),
                            "pre_market_change_percent": quote.get('preMarketChangePercent'),
                            "is_market_open": quote.get('marketState') == 'REGULAR',
                            "last_updated": "Real-time via Quote API"
                        }
        except Exception as e:
            print(f"⚠️ Quote API failed for {symbol}: {e}")
        
        return None

    async def get_price(self, symbol: str) -> dict:
        """Get current price and market data for a symbol from Yahoo Finance with rate limiting"""
        # Check cache with TTL (time-to-live) for real-time updates
        current_time = time.time()
        if (symbol in self.cache and 
            symbol in self.cache_timestamps and 
            current_time - self.cache_timestamps[symbol] < self.cache_ttl):
            return self.cache[symbol]
        
        # Apply rate limiting before making API request
        self._rate_limit_request()
        
        # Try direct Yahoo Finance API first (more reliable for cloud deployments)
        direct_result = await self.get_price_from_yahoo_direct(symbol)
        if direct_result:
            # Success! Reset failure counter and cache the result
            self.consecutive_failures = 0
            self.success_count += 1
            self.cache[symbol] = direct_result
            self.cache_timestamps[symbol] = current_time
            trend = "📈" if direct_result['change'] >= 0 else "📉"
            print(f"✅ Direct Yahoo API SUCCESS: {symbol} = {direct_result['currency']}{direct_result['price']:.2f} ({trend} {direct_result['change']:+.2f}, {direct_result['change_percent']:+.2f}%) - Success #{self.success_count}")
            return direct_result
        else:
            # Direct API failed, increment failure counter
            self.consecutive_failures += 1
            print(f"❌ Direct Yahoo API failed for {symbol} - Failure #{self.consecutive_failures}")
        
        # Fallback to yfinance library
        try:
            ticker = yf.Ticker(symbol)
            
            # Try multiple methods to get price data
            price = None
            info = None
            
            # Method 1: Try to get info (most comprehensive but can fail with 429)
            try:
                info = ticker.info
                if 'currentPrice' in info and info['currentPrice']:
                    price = float(info['currentPrice'])
                elif 'regularMarketPrice' in info and info['regularMarketPrice']:
                    price = float(info['regularMarketPrice'])
                elif 'previousClose' in info and info['previousClose']:
                    price = float(info['previousClose'])
                    
                # Success - reset consecutive failures
                if price and price > 0:
                    self.consecutive_failures = 0
                    self.success_count += 1
                    
            except Exception as e:
                self.consecutive_failures += 1
                print(f"⚠️ Method 1 (info) failed for {symbol}: {e}")
                # Check if it's a rate limit error
                if "429" in str(e) or "Too Many Requests" in str(e):
                    print(f"🚫 Rate limit hit for {symbol}, consecutive failures: {self.consecutive_failures}")
                    # Skip to fallback immediately for rate limit errors
                    price = None
            
            # Method 2: Try history if info failed (more reliable for basic price)
            if price is None or price <= 0:
                try:
                    hist = ticker.history(period="1d", interval="5m")
                    if not hist.empty and 'Close' in hist.columns:
                        price = float(hist['Close'].iloc[-1])
                        print(f"📊 Using history method for {symbol}: ${price:.2f}")
                        # Success - reset consecutive failures
                        self.consecutive_failures = 0
                        self.success_count += 1
                except Exception as e:
                    self.consecutive_failures += 1
                    print(f"⚠️ Method 2 (history) failed for {symbol}: {e}")
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        print(f"🚫 Rate limit hit on history for {symbol}, consecutive failures: {self.consecutive_failures}")
            
            if price and price > 0:
                currency = self.get_currency_symbol(symbol, info or {})
                
                # Get additional market data if info is available
                if info:
                    change = info.get('regularMarketChange', 0.0)
                    day_high = info.get('regularMarketDayHigh', price)
                    day_low = info.get('regularMarketDayLow', price)
                    previous_close = info.get('regularMarketPreviousClose', price)
                    
                    # Calculate change percentage manually for accuracy
                    change_percent = (change / previous_close * 100) if previous_close != 0 else 0.0
                    
                    # Pre-market data if available
                    pre_market_price = info.get('preMarketPrice')
                    pre_market_change = info.get('preMarketChange', 0.0)
                    pre_market_change_percent = (pre_market_change / previous_close * 100) if previous_close != 0 and pre_market_price else 0.0
                else:
                    # Basic data when only price is available
                    change = 0.0
                    change_percent = 0.0
                    day_high = price
                    day_low = price
                    previous_close = price
                    pre_market_price = None
                    pre_market_change = None
                    pre_market_change_percent = None
                
                result = {
                    "symbol": symbol,
                    "price": price,
                    "currency": currency,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "day_high": day_high,
                    "day_low": day_low,
                    "previous_close": previous_close,
                    "pre_market_price": pre_market_price,
                    "pre_market_change": round(pre_market_change, 2) if pre_market_price else None,
                    "pre_market_change_percent": round(pre_market_change_percent, 2) if pre_market_price else None,
                    "is_market_open": info.get('regularMarketTime') is not None if info else True,
                    "last_updated": info.get('regularMarketTime', 'Real-time') if info else 'Real-time'
                }
                
                self.cache[symbol] = result
                self.cache_timestamps[symbol] = current_time
                trend = "📈" if change >= 0 else "📉"
                print(f"✅ Yahoo Finance: {symbol} = {currency}{price:.2f} ({trend} {change:+.2f}, {change_percent:+.2f}%)")
                return result
            else:
                print(f"⚠️ Yahoo Finance returned invalid price for {symbol}, using fallback")
                
        except Exception as e:
            self.consecutive_failures += 1
            print(f"⚠️ Yahoo Finance error for {symbol}: {e}, using fallback")
        
        # Final fallback to simulated prices (with small random variations for demo)
        base_price = self._fallback_prices.get(symbol, 100.0)
        # Add small random variation (-2% to +2%) to simulate price changes
        price_variation = random.uniform(-0.02, 0.02)
        fallback_price = round(base_price * (1 + price_variation), 2)
        previous_close = base_price  # Keep base as previous close
        
        # Calculate change from base price
        change = fallback_price - previous_close
        change_percent = round((change / previous_close) * 100, 2)
        
        currency = self.get_currency_symbol(symbol, {})
        print(f"📊 Using simulated price for {symbol}: {currency}{fallback_price} (change: {change:+.2f}) - Consecutive failures: {self.consecutive_failures}")
        
        return {
            "symbol": symbol,
            "price": fallback_price, 
            "currency": currency,
            "change": change,
            "change_percent": change_percent,
            "day_high": max(fallback_price, previous_close),
            "day_low": min(fallback_price, previous_close),
            "previous_close": previous_close,
            "pre_market_price": None,
            "pre_market_change": None,
            "pre_market_change_percent": None,
            "is_market_open": False,
            "last_updated": f"Fallback data (rate limited - {self.consecutive_failures} failures)"
        }
    
    async def get_multiple_prices(self, symbols: List[str]) -> Dict[str, dict]:
        """Get prices for multiple symbols with enhanced rate limiting"""
        prices = {}
        for i, symbol in enumerate(symbols):
            price_data = await self.get_price(symbol)
            prices[symbol] = price_data
            
            # Progressive delay to be more conservative with multiple requests
            if i < len(symbols) - 1:  # Don't sleep after the last symbol
                delay = min(0.5 + (i * 0.1), 2.0)  # Progressive delay: 0.5s, 0.6s, 0.7s... up to 2s
                print(f"⏱️ Waiting {delay:.1f}s before next request ({i+1}/{len(symbols)} completed)")
                await asyncio.sleep(delay)
        
        return prices

# Initialize pricing service
pricing_service = PricingService()

@app.get("/")
def health():
    return {"agent": "PricingAgent", "status": "healthy", "version": "1.0.0"}

@app.get("/.well-known/agent-card")
def agent_card():
    """A2A Agent Discovery Endpoint"""
    return JSONResponse(
        content={
            "name": "PricingAgent",
            "version": "1.0.0",
            "description": "Specialized agent for market data and stock pricing",
            "endpoints": {
                "price": "/price/{symbol}",
                "multiple_prices": "/prices",
                "health": "/health"
            },
            "capabilities": [
                "stock.pricing",
                "market.data", 
                "alphavantage.integration"
            ],
            "port": 8001,
            "streams": False,
            "auth": "none"
        }
    )

@app.get("/price/{symbol}")
async def get_single_price(symbol: str):
    """Get comprehensive price and market data for a single stock symbol"""
    try:
        price_data = await pricing_service.get_price(symbol.upper())
        # Return all the rich data from Yahoo Finance
        result = price_data.copy()
        result.update({
            "source": "yahoo_finance",
            "agent": "PricingAgent"
        })
        return result
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

@app.get("/price/{symbol}")
async def get_single_price(symbol: str):
    """Get price for a single stock symbol (compatible with orchestrator)"""
    try:
        price_data = await pricing_service.get_price(symbol.upper())
        return price_data
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

@app.post("/prices")
async def get_multiple_prices(symbols: List[str]):
    """Get prices for multiple stock symbols"""
    try:
        prices = await pricing_service.get_multiple_prices([s.upper() for s in symbols])
        return {
            "prices": prices,
            "source": "yahoo_finance",
            "agent": "PricingAgent"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health_status():
    """Get detailed health status"""
    return {
        "agent": "PricingAgent",
        "status": "healthy",
        "data_source": "yahoo_finance",
        "cache_size": len(pricing_service.cache),
        "fallback_symbols": len(pricing_service._fallback_prices),
        "capabilities": ["stock.pricing", "market.data", "yahoo.finance.integration"]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PRICING_AGENT_PORT", "8011"))
    uvicorn.run(app, host="0.0.0.0", port=port)
