# Setup Guide

## Prerequisites
- Python 3.12+
- Azure OpenAI access

## Installation

### Step 1: Python Environment
```bash
# Clone and navigate to project
cd a2a-milan

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements_sk.txt
```

### Step 2: Azure OpenAI Setup

#### Create Azure OpenAI Resource
1. Go to [Azure Portal](https://portal.azure.com)
2. Search for "Azure OpenAI" → Click "Create"  
3. Fill in: Resource Group, Region (e.g., East US), Name, Pricing Tier (S0)
4. Deploy a model: Go to your resource → "Model deployments" → Deploy `gpt-4o-mini`

#### Configure Environment
Create `.env` file in root directory:
```bash
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

Get these values from: Azure Portal → Your OpenAI Resource → "Keys and Endpoint"
- Free tier: 25 requests/day, 5 per minute
- Fallback simulation activates when limits reached

### Step 3: System Testing

#### A2A System Test (Current Semantic Kernel Implementation)
```bash
# Run the AI-powered wealth management system
./start_agents_sk.sh

# Services will start on:
# - Orchestrator: http://localhost:8010
# - Pricing: http://localhost:8011
# - Rebalance: http://localhost:8012

# Access dashboard: open static/index.html in browser

# Terminal 3  
python agents_sk/market_agent.py

# Test: http://localhost:8010
```

## Troubleshooting

### Common Issues
### System Health Check
```bash
# Check system status
./test_system.sh

# Individual agent health checks:
curl http://localhost:8010/health  # Orchestrator
curl http://localhost:8011/health  # Pricing
curl http://localhost:8012/health  # Rebalance
```

### Known Issues

1. **Port conflicts**: Ensure ports 8010-8012 are available
2. **OpenAI quota**: Monitor usage and check quotas if requests fail
3. **Network issues**: Yahoo Finance API may be rate-limited during market hours
4. **Memory usage**: System requires ~200MB RAM for optimal performance

### System Validation
- Check agent registration at startup logs
- Verify UI loads at correct ports
- Test basic queries: "Show my portfolio"
- Monitor logs/ directory for detailed output

## Development Notes

### Agent Communication Flow
1. User → UI → Orchestrator
2. Orchestrator → Specialized Agents (Portfolio/Market/Rebalance)
3. Agents → Process & Respond
4. Orchestrator → Aggregate & Return

### Key Differences
- **Custom**: Manual HTTP calls, direct control
- **Semantic Kernel**: Framework-managed, AI-enhanced

### Performance Comparison
- **Custom**: ~50ms response time
- **SK**: ~150ms response time (due to AI processing)

Choose based on needs:
- Learning/Performance: Custom A2A
- Enterprise/AI: Semantic Kernel A2A
