# 🤖 AI Portfolio Management System

A sophisticated multi-agent AI system for portfolio management with **Microsoft Semantic Kernel 1.37**, FastAPI, and Azure OpenAI.

## 🔗 Quick Links

- 📋 **[Documentation Index](docs/README.md)** - Complete documentation organized by audience  
- 🏗️ **[Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md)** - System design & infrastructure

## 🎯 What It Does

**Advanced AI-Powered Wealth Management** with 3 agents + 6 AI plugins:
- 🤖 **3 Microservice Agents** - Orchestrator, Pricing, Rebalancing services
- 🧠 **6 AI Plugins** in Orchestrator - Semantic Kernel 1.37 intelligence
- 💰 **Real-time Stock Pricing** - Live Yahoo Finance integration
- ⚖️ **Portfolio Rebalancing** - AI-optimized allocation strategies  
- 🔍 **Market Sentiment Analysis** - AI news analysis & sentiment scoring
- 📈 **Transaction History Intelligence** - Contextual trading analysis

## 🚀 Quick Start

### 1. Deploy to Azure
```bash
./deploy.sh
```

### 2. Access the Web UI
The deployment script will provide the Azure Container Apps URL

### 3. Try It Out
**Advanced AI Conversations:**

**🔍 Risk Analysis:**
- *"Analyze the risk-adjusted returns of my portfolio and suggest optimal rebalancing strategies based on recent market volatility"*

**📈 Strategic Planning:**
- *"Given the current economic indicators and Fed policy outlook, how should I adjust my tech vs value allocation for the next quarter?"*

**⚖️ Portfolio Optimization:**
- *"Rebalance my portfolio to achieve 25% growth, 35% dividend yield, 40% defensive positioning"*

**🎯 Diversification Strategy:**
- *"Assess correlation risks in my holdings and recommend diversification strategies that maintain my target 8% annual return while reducing portfolio beta"*

## 🏗️ Architecture

### 3 Microservice Agents

1. **Orchestrator** (Port 8010) 🧠
   - **Microsoft Semantic Kernel 1.37** with 6 AI plugins
   - Web UI hosting and AI conversation management
   - Advanced portfolio intelligence and decision making

2. **Pricing** (Port 8011) 💰
   - Yahoo Finance integration
   - Real-time stock prices
   - Multi-currency support

3. **Rebalance** (Port 8012) ⚖️
   - **Complete Portfolio Rebalancing** - Current vs target allocation analysis
   - **Smart Trade Generation** - Buy/sell recommendations with constraints
   - **Risk Management** - Max turnover % and minimum trade value controls
   - **Real-time Calculations** - Uses live prices for accurate rebalancing

### 6 AI Plugins (in Orchestrator)
- 💰 **Stock Pricing Plugin** - Real-time market data
- ⚖️ **Portfolio Rebalancing Plugin** - Smart allocation management
- 📊 **Market Insights Plugin** - Educational financial concepts
- 🔍 **Market Sentiment Plugin** - AI sentiment analysis & news intelligence
- 📈 **Transaction History Plugin** - Contextual trading analysis
- 🧠 **Performance Analysis Plugin** - Historical performance insights

## ✨ Key Features

### 🧠 Advanced AI Intelligence
The AI automatically orchestrates specialized functions:

**Stock Intelligence:**
- Real-time pricing with currency support
- AI sentiment analysis & news intelligence
- Market buzz and trend analysis

**Portfolio Intelligence:**  
- Advanced portfolio valuation and breakdown
- Smart current vs target allocation comparison
- AI-optimized buy/sell recommendations with risk management

**Transaction Intelligence:**
- Contextual trading analysis and performance insights
- Educational financial concepts and rationale
- Historical context and market intelligence

### ⚖️ Complete Portfolio Rebalancing
**AI-Powered Allocation Management:**
- 📊 **Real-time Portfolio Valuation** - Live Yahoo Finance pricing
- 🎯 **Target vs Current Analysis** - Precise allocation percentage comparison  
- 💰 **Smart Trade Generation** - Specific buy/sell recommendations with dollar amounts
- ⚠️ **Risk Management** - Maximum turnover % and minimum trade value controls
- 🔼 **Action Recommendations** - Clear BUY/SELL instructions with quantities

### 🎯 Enterprise-Grade AI Output
Advanced AI insights with professional formatting:
- 📊 **Portfolio Analytics** - Real-time value calculations & breakdowns
- ⚖️ **Rebalancing Intelligence** - Complete current → target allocation analysis
- 💰 **Trading Recommendations** - AI-optimized strategies with constraint management
- 🔍 **Market Sentiment** - News analysis, sentiment scoring, market buzz
- 📈 **Historical Context** - Transaction-based performance analysis
- 🧠 **Contextual Insights** - AI-powered rationale and educational guidance

## 🔧 Configuration

### Prerequisites
- Azure CLI installed and authenticated
- Docker installed and running
- Azure OpenAI access with gpt-4o-mini deployment

### Environment Setup
The deployment script automatically configures:
- Azure Container Apps environment
- Azure OpenAI integration
- Container Registry and Key Vault
- Managed identities and secrets

## 🛑 Cleanup Resources
```bash
./cleanup.sh
```

## 💻 Tech Stack
- **AI Framework**: Microsoft Semantic Kernel 1.37
- **Backend**: FastAPI with Python 3.12
- **AI Model**: Azure OpenAI (gpt-4o-mini)
- **Data Source**: Yahoo Finance API
- **Infrastructure**: Azure Container Apps, Bicep
- **Performance**: 98% optimized (1.2s response time)

## 📁 Project Structure
```
wealth-management-agent/
├── agents/              # 3 Microservice Agents
│   ├── orchestrator/    # AI brain + 6 SK plugins  
│   ├── pricing/         # Yahoo Finance integration
│   └── rebalance/       # Portfolio calculations
├── infra/               # Infrastructure as Code (Bicep)
├── static/              # Web UI dashboard  
├── deploy.sh            # Azure deployment script
├── cleanup.sh           # Resource cleanup script
├── Dockerfile.*         # Container definitions
└── requirements_sk.txt  # Python dependencies
```

## 📚 Documentation

📋 **[Complete Documentation Index](docs/README.md)** - Organized by audience and use case

**Quick Links:**
- 🏗️ **[Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md)** - Complete system design & Azure infrastructure
- 🚀 **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Azure production deployment
- 🧑‍💻 **[Setup Guide](docs/SETUP_GUIDE.md)** - Local development environment  
- 🧪 **[Testing Guide](docs/UI_TESTING_GUIDE.md)** - QA procedures and troubleshooting

## 🎓 Learn More

This system demonstrates enterprise-grade AI portfolio management with:
- **98% performance optimization** (62s → 1.2s response times)
- **Production-ready deployment** to Azure Container Apps
- **Advanced AI reasoning** with Microsoft Semantic Kernel
- **Real-time market integration** and portfolio intelligence

---

**Built with ❤️ using Microsoft Semantic Kernel 1.37**