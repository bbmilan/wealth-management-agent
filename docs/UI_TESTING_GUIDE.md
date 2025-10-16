# 🧪 Quality Assurance & Testing Guide

*This guide is designed for developers, QA engineers, and technical stakeholders who need to validate system functionality and troubleshoot issues.*

## ✅ System Status

### Production Environment (Azure)
- **Orchestrator**: https://orchestrator.purplerock-e79b7ad9.uksouth.azurecontainerapps.io
- **Pricing**: https://pricing.purplerock-e79b7ad9.uksouth.azurecontainerapps.io  
- **Rebalance**: https://rebalance.purplerock-e79b7ad9.uksouth.azurecontainerapps.io

### Local Development (Optional)
- **Orchestrator**: http://localhost:8010 (AI brain + UI host)
- **Pricing**: http://localhost:8011 (Yahoo Finance integration)
- **Rebalance**: http://localhost:8012 (Portfolio calculations)

## 🚀 Quick Start

### 1. Start the System
```bash
./scripts/start_system.sh
```

### 2. Access the Dashboard
**Production URL**: https://orchestrator.purplerock-e79b7ad9.uksouth.azurecontainerapps.io
**Local URL** (if running locally): http://localhost:8010

**Features**:
- 📊 **Professional Dashboard** - Real-time portfolio view with 5 stocks
- 💰 **Live Price Updates** - Yahoo Finance integration with flash animations  
- 🤖 **AI Chat Interface** - Semantic Kernel-powered conversations
- 📈 **Portfolio Analytics** - Real-time total value calculations
- 🎯 **"Veltrax Capital - Private Wealth Management"** branding

## 💼 Built-in Portfolio Knowledge

**Important**: The AI agent already knows your portfolio holdings:
- **AAPL** (Apple Inc.) - Technology growth stock
- **MSFT** (Microsoft Corp.) - Technology value stock  
- **LLOY.L** (Lloyds Banking Group) - UK financial sector
- **SHEL** (Shell plc) - Energy/dividend stock
- **TSLA** (Tesla Inc.) - Growth/electric vehicle stock

**No need to specify holdings** - Just ask natural questions like "analyze my portfolio" or "rebalance my holdings."

## 🧪 AI Test Scenarios

### Test 1: Advanced Portfolio Risk Analysis
**What to type**: "Analyze the risk-adjusted returns of my portfolio and suggest optimal rebalancing strategies based on recent market volatility"

**Expected**: 
- AI automatically accesses your known portfolio holdings (AAPL, MSFT, LLOY.L, SHEL, TSLA)
- Calculates Sharpe ratio, beta, Value at Risk (VaR) metrics
- Analyzes correlation matrix between your holdings
- Provides sophisticated rebalancing recommendations with risk justification

### Test 2a: Macroeconomic Strategy Planning
**What to type**: "Given the current economic indicators and Fed policy outlook, how should I adjust my tech vs value allocation for the next quarter?"

**Expected**: AI provides strategic asset allocation guidance using your existing portfolio

### Test 2b: Advanced Multi-Objective Rebalancing  
**What to type**: "Rebalance my portfolio to achieve 25% growth, 35% dividend yield, 40% defensive positioning"

**Expected AI Process**:
1. **Accesses your known portfolio** (built-in holdings: AAPL, MSFT, LLOY.L, SHEL, TSLA)
2. **Gets real-time prices** from Yahoo Finance for all your symbols
3. **Calculates total portfolio value** using current market prices
4. **Analyzes current allocation** across growth/dividend/defensive categories
5. **Maps your holdings to investment styles** (TSLA=growth, SHEL=dividend, etc.)
6. **Generates strategic trades** to achieve target style allocation
7. **Applies modern portfolio theory constraints** (risk-return optimization)
8. **Provides institutional-grade HTML output** with sector analysis and risk metrics

### Test 3: Portfolio Correlation and Diversification Analysis
**What to type**: "Assess correlation risks in my holdings and recommend diversification strategies that maintain my target 8% annual return while reducing portfolio beta" 

**Expected**:
- AI analyzes correlation between your known holdings (AAPL, MSFT, LLOY.L, SHEL, TSLA)
- Calculates portfolio beta and provides risk-return optimization suggestions
- Total cost basis and performance analysis

**Alternative**: "Analyze my portfolio performance" uses all built-in transaction data

### Test 4: Portfolio Rebalancing with Constraints
**What to type**: "Rebalance my current portfolio but keep turnover under 50% and minimum trade of $1000"

**Expected**:
- AI applies risk management constraints
- Only suggests trades above $1000 minimum
- Calculates turnover percentage and stays within limits
- Explains any trades skipped due to constraints

### Test 5: Advanced Portfolio Analysis
**What to type**: "How has my portfolio performed based on my trading history?"

**Expected**:
- AI calls pricing for all symbols
- Calculates total value
- Shows breakdown by stock

### Test 4: Portfolio Rebalancing 🎯 **AI-POWERED**
**What to type**: 
```
Rebalance my portfolio to equal weights across all holdings
```

**Alternative test**:
```
I want to change my allocation to 40% tech stocks and 60% traditional stocks
```

**Expected**:
- AI calls multiple functions automatically:
  1. Calculate portfolio value
  2. Analyze current allocation
  3. Generate trade recommendations
- Returns clean HTML with:
  - 📊 Current Portfolio Summary
  - ⚖️ Allocation Analysis (with ✅ ⚠️ ❌ indicators)
  - 💰 Recommended Trades (🔼 BUY / 🔽 SELL)
  - 🎯 Professional Rationale

### Test 5: Context Awareness
**First message**: "What is MSFT trading at?"
**Second message**: "What about GOOGL?"

**Expected**:
- Understands "What about" refers to stock price
- Maintains conversation context

### Test 6: Market Insights
**What to type**: "Give me market insights on the tech sector"

**Expected**:
- AI provides market analysis
- May include sentiment and trends

## 🎨 What to Look For

### Good Signs ✅
1. **Clean HTML output** - Not raw markdown like `### Header`
2. **Proper formatting** - Headers, bullets, bold text render correctly
3. **Emojis display** - 📊 ⚖️ 💰 🎯 show properly
4. **Visual indicators** - ✅ (good), ⚠️ (warning), ❌ (bad) for allocations
5. **Professional language** - Sounds like a financial advisor
6. **Action clarity** - 🔼 BUY / 🔽 SELL with exact quantities

### Bad Signs ❌
1. Raw markdown text (###, **, etc.)
2. Escaped characters (\n, \t)
3. Missing line breaks
4. Generic responses without function calls
5. Error messages in red

## 🔧 Troubleshooting

### If UI doesn't load:
```bash
# Check orchestrator is running
curl http://localhost:8010/health

# Check static files are mounted
ls -la /Users/milanjugovic/a2a-milan/static/
```

### If stock prices fail:
```bash
# Check pricing agent
curl http://localhost:8011/health

# Test direct price lookup
curl -X POST http://localhost:8011/prices \
  -H "Content-Type: application/json" \
  -d '["AAPL", "MSFT"]'
```

### If rebalancing doesn't work:
```bash
# Check rebalance agent  
curl http://localhost:8012/health

# Test AI-powered endpoint directly
curl -X POST http://localhost:8012/rebalance/plan/ai \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio": {
      "positions": [
        {"symbol": "AAPL", "quantity": 50, "avgCost": 150.0}
      ]
    },
    "targets": {"AAPL": 1.0},
    "constraints": {"maxTurnover": 0.3, "minTradeValue": 100}
  }'
```

### If nothing works:
```bash
# Restart all agents
cd /Users/milanjugovic/a2a-milan
pkill -f "agents/"
sleep 2

# Start agents
source .venv/bin/activate
python agents/pricing/main.py &
sleep 2
python agents/orchestrator/main.py &
sleep 2
uvicorn agents.rebalance.main:app --port 8012 &
```

## 📊 Backend Verification

### Check Auto Function Calling
Monitor the logs to see SK's automatic function calling:

```bash
# Watch rebalance agent logs
tail -f /tmp/rebalance.log

# Look for lines like:
# "SK function called: calculate_portfolio_value"
# "SK function called: analyze_portfolio_allocation"
# "SK function called: generate_rebalance_trades"
```

### Check OpenAI API Calls
```bash
# Watch orchestrator logs
tail -f logs/orchestrator.log

# Look for Azure OpenAI API calls
# Should see model: gpt-4o-mini, luxdemo deployment
```

## 🎯 Success Criteria

You'll know everything is working when:
1. ✅ Stock prices return in < 2 seconds
2. ✅ Portfolio rebalancing shows clean HTML (not markdown)
3. ✅ AI automatically calls 3 functions for rebalancing
4. ✅ Output includes visual indicators (✅ ⚠️ ❌)
5. ✅ Recommendations sound professional and actionable
6. ✅ No error messages in UI
7. ✅ All emojis render properly

## 📸 Screenshot Comparison

**Before** (your screenshot): Raw text with ### and escaped chars
**After** (now): Clean HTML with proper headers, bullets, and formatting

See `test_rebalance_output.html` for a visual example of the expected output.

## 🚀 Next Steps After Testing

If everything works:
1. Try different portfolio combinations
2. Test with international stocks (LLOY.L, etc.)
3. Experiment with different target allocations
4. Try conversational follow-ups ("What if I want 50% AAPL instead?")

Have fun testing! 🎉
