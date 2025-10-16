# Infrastructure as Code - Azure Deployment

This directory contains Bicep templates for deploying the AI Portfolio Management System to Azure using Azure Developer CLI (azd).

## 🏗️ Architecture

The infrastructure deploys a complete microservices architecture:

- **3 Container Apps** (Orchestrator, Pricing, Rebalance)  
- **Azure OpenAI Service** (gpt-4o-mini)
- **Container Registry** (for container images)
- **Key Vault** (secure secret storage)
- **Application Insights** (monitoring)
- **Log Analytics** (centralized logging)

## 📁 Files

- `main.bicep` - Main infrastructure template
- `main.parameters.json` - Environment parameters
- `azure.yaml` - Azure Developer CLI configuration
- `Dockerfile.*` - Container definitions for each service

## 🚀 Deployment

### Prerequisites

1. **Install Azure CLI**
   ```bash
   # macOS
   brew install azure-cli
   
   # Login to Azure
   az login
   ```

2. **Install Azure Developer CLI**
   ```bash
   # macOS
   brew tap azure/azd && brew install azd
   ```

3. **Install Docker**
   ```bash
   # macOS
   brew install docker
   ```

### Deploy to Azure

1. **Initialize the environment**
   ```bash
   azd init
   ```

2. **Preview the deployment** (recommended)
   ```bash
   azd provision --preview
   ```

3. **Deploy everything**
   ```bash
   azd up
   ```

4. **Access the application**
   ```bash
   # Get the URLs
   azd show
   ```

## 🔧 Configuration

### Required Secrets

The deployment will prompt for:
- Azure OpenAI API key (stored in Key Vault)

### Environment Variables

Set in Azure Container Apps:
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI service endpoint
- `AZURE_OPENAI_DEPLOYMENT` - Model deployment name (gpt-4o-mini)
- `AZURE_OPENAI_API_KEY` - API key (from Key Vault)

## 🏥 Monitoring

- **Application Insights**: Performance monitoring and telemetry
- **Log Analytics**: Centralized logging for all services
- **Health Checks**: Built-in health endpoints for each service

## 🛡️ Security

- **Managed Identity**: All services use User-Assigned Managed Identity
- **Key Vault**: Secure storage for secrets
- **RBAC**: Least privilege access controls
- **HTTPS**: All external traffic encrypted

## 🔄 CI/CD Integration

The infrastructure supports automated deployment through:
- Azure DevOps Pipelines
- GitHub Actions  
- Manual deployment via `azd`

## 📊 Cost Estimation

**Monthly costs (estimated):**
- Container Apps: ~$20-50 (consumption-based)
- Azure OpenAI: ~$10-30 (usage-based)  
- Container Registry: ~$5 (Basic tier)
- Key Vault: ~$3 (operations-based)
- Monitoring: ~$10 (data ingestion)

**Total: ~$50-100/month** (varies by usage)

## 🧹 Cleanup

To delete all resources:
```bash
azd down --purge
```

## 🆘 Troubleshooting

1. **Check deployment logs**
   ```bash
   azd logs
   ```

2. **Verify Container App health**
   ```bash
   az containerapp show --name orchestrator --resource-group <rg-name>
   ```

3. **Check Azure OpenAI quota**
   ```bash
   az cognitiveservices account list-usage --name <openai-name> --resource-group <rg-name>
   ```

## 📚 References

- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure OpenAI Documentation](https://docs.microsoft.com/azure/cognitive-services/openai/)
- [Azure Developer CLI Documentation](https://docs.microsoft.com/azure/developer/azure-developer-cli/)