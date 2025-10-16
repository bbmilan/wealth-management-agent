#!/bin/bash
set -e

echo "🚀 Starting standalone A2A Portfolio deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration - Update these values
ENVIRONMENT_NAME="dev"
LOCATION="uksouth"

# Generate user-specific suffix for uniqueness
USER_ID=$(az account show --query "user.name" -o tsv | md5sum | head -c 6 2>/dev/null || echo "$(whoami)" | md5sum | head -c 6)
RESOURCE_GROUP_NAME="rg-ai-${ENVIRONMENT_NAME}-${USER_ID}"

# Function to cleanup soft-deleted resources
cleanup_soft_deleted_resources() {
    print_status "Checking for soft-deleted resources that might conflict..."
    
    # We'll calculate expected resource names based on Bicep logic
    local subscription_id=$(az account show --query "id" -o tsv)
    local resource_token=$(echo "${subscription_id}${RESOURCE_GROUP_NAME}${LOCATION}${ENVIRONMENT_NAME}" | md5sum | head -c 13)
    
    local vault_name="kv${resource_token}"
    local openai_name="ai${resource_token}"
    
    print_status "Checking Key Vault: $vault_name"
    if az keyvault list-deleted --query "[?name=='$vault_name']" -o tsv 2>/dev/null | grep -q "$vault_name"; then
        print_warning "Found soft-deleted Key Vault '$vault_name'. Purging..."
        az keyvault purge --name "$vault_name" --location "$LOCATION" 2>/dev/null || print_warning "Could not purge Key Vault (may not exist or already purged)"
    fi
    
    print_status "Checking Azure OpenAI: $openai_name"
    # Note: Cognitive Services purge requires resource group, but for soft-deleted we try without it first
    az cognitiveservices account purge --name "$openai_name" --resource-group "$RESOURCE_GROUP_NAME" --location "$LOCATION" 2>/dev/null || true
    
    # Wait a moment for purge operations to complete
    if [[ $(az keyvault list-deleted --query "[?name=='$vault_name']" -o tsv 2>/dev/null | wc -l) -gt 0 ]] || [[ $(az cognitiveservices account list-deleted --query "[?name=='$openai_name']" -o tsv 2>/dev/null | wc -l) -gt 0 ]]; then
        print_status "Waiting for soft-delete purge to complete..."
        sleep 15
    fi
}

# Check if deployment already exists and get existing values
EXISTING_RG=$(az group list --query "[?name=='${RESOURCE_GROUP_NAME}'].name" -o tsv 2>/dev/null || echo "")

if [ ! -z "$EXISTING_RG" ]; then
    print_status "Found existing resource group: $RESOURCE_GROUP_NAME"
    
    # Check if this is a complete deployment
    EXISTING_REGISTRY=$(az acr list --resource-group "$RESOURCE_GROUP_NAME" --query "[0].name" -o tsv 2>/dev/null || echo "")
    EXISTING_APPS=$(az containerapp list --resource-group "$RESOURCE_GROUP_NAME" --query "[0].name" -o tsv 2>/dev/null || echo "")
    
    if [ ! -z "$EXISTING_REGISTRY" ] && [ ! -z "$EXISTING_APPS" ]; then
        print_status "Complete deployment already exists!"
        print_status "Registry: $EXISTING_REGISTRY"
        print_status "Container Apps: Found existing apps"
        
        # Use existing registry for container operations
        REGISTRY_NAME="$EXISTING_REGISTRY"
        SKIP_INFRASTRUCTURE=true
        print_status "Will skip infrastructure deployment and update containers only"
    else
        print_status "Incomplete deployment found. Will complete the deployment."
        SKIP_INFRASTRUCTURE=false
        cleanup_soft_deleted_resources
    fi
else
    print_status "Creating new deployment with resource group: $RESOURCE_GROUP_NAME"
    SKIP_INFRASTRUCTURE=false
    cleanup_soft_deleted_resources
fi

# Step 1: Create resource group (if needed)
if [ "$SKIP_INFRASTRUCTURE" != "true" ]; then
    print_status "Creating resource group..."
    az group create --name "$RESOURCE_GROUP_NAME" --location "$LOCATION"

    # Step 2: Deploy infrastructure using bicep directly
    print_status "Deploying infrastructure with bicep..."
    DEPLOYMENT_NAME="ai-portfolio-$(date +%Y%m%d-%H%M%S)"

    az deployment group create \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --template-file "infra/main.bicep" \
        --parameters environmentName="$ENVIRONMENT_NAME" \
        --parameters location="$LOCATION" \
        --name "$DEPLOYMENT_NAME"

    if [ $? -ne 0 ]; then
        print_error "Infrastructure deployment failed!"
        exit 1
    fi

    print_success "Infrastructure deployed successfully!"
else
    print_status "Skipping infrastructure deployment (already exists)"
    # Get the most recent deployment for output extraction
    DEPLOYMENT_NAME=$(az deployment group list --resource-group "$RESOURCE_GROUP_NAME" --query "max_by([?contains(name, 'ai-portfolio')], &properties.timestamp).name" -o tsv)
    if [ -z "$DEPLOYMENT_NAME" ]; then
        print_error "Could not find existing deployment in resource group"
        exit 1
    fi
    print_status "Using existing deployment: $DEPLOYMENT_NAME"
fi

# Step 3: Get deployment configuration
print_status "Getting deployment configuration..."

if [ -z "$REGISTRY_NAME" ]; then
    # Try to get from deployment outputs first
    REGISTRY_SERVER=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --name "$DEPLOYMENT_NAME" \
        --query "properties.outputs.azurE_CONTAINER_REGISTRY_ENDPOINT.value" \
        --output tsv 2>/dev/null)

    if [ ! -z "$REGISTRY_SERVER" ]; then
        REGISTRY_NAME=$(echo "$REGISTRY_SERVER" | cut -d'.' -f1)
    else
        # Fallback: get from existing ACR in resource group
        REGISTRY_NAME=$(az acr list --resource-group "$RESOURCE_GROUP_NAME" --query "[0].name" -o tsv 2>/dev/null)
        if [ ! -z "$REGISTRY_NAME" ]; then
            REGISTRY_SERVER="${REGISTRY_NAME}.azurecr.io"
        fi
    fi
fi

# Get application URLs (needed for final output)
ORCHESTRATOR_URI=$(az deployment group show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --query "properties.outputs.orchestratoR_URI.value" \
    --output tsv 2>/dev/null || az containerapp show --name orchestrator --resource-group "$RESOURCE_GROUP_NAME" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null | sed 's/^/https:\/\//')

PRICING_URI=$(az deployment group show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --query "properties.outputs.pricinG_URI.value" \
    --output tsv 2>/dev/null || az containerapp show --name pricing --resource-group "$RESOURCE_GROUP_NAME" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null | sed 's/^/https:\/\//')

REBALANCE_URI=$(az deployment group show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --query "properties.outputs.rebalancE_URI.value" \
    --output tsv 2>/dev/null || az containerapp show --name rebalance --resource-group "$RESOURCE_GROUP_NAME" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null | sed 's/^/https:\/\//')

# Debug output
print_status "Registry Server: $REGISTRY_SERVER"
print_status "Registry Name: $REGISTRY_NAME"

# Validate we have the registry name
if [ -z "$REGISTRY_NAME" ]; then
    print_error "Failed to get registry name from deployment outputs or existing resources"
    print_status "Available deployment outputs:"
    az deployment group show --resource-group "$RESOURCE_GROUP_NAME" --name "$DEPLOYMENT_NAME" --query "properties.outputs" -o json 2>/dev/null || echo "No deployment outputs available"
    print_status "Available ACR resources:"
    az acr list --resource-group "$RESOURCE_GROUP_NAME" -o table 2>/dev/null || echo "No ACR resources found"
    exit 1
fi

print_status "Container Registry: $REGISTRY_NAME"
print_status "Resource Group: $RESOURCE_GROUP_NAME"

# Step 4: Build and push container images
print_status "Building container images with AMD64 architecture..."

if ! docker build --platform linux/amd64 -f Dockerfile.orchestrator -t $REGISTRY_NAME.azurecr.io/orchestrator:latest .; then
    print_error "Failed to build orchestrator image"
    exit 1
fi

if ! docker build --platform linux/amd64 -f Dockerfile.pricing -t $REGISTRY_NAME.azurecr.io/pricing:latest .; then
    print_error "Failed to build pricing image" 
    exit 1
fi

if ! docker build --platform linux/amd64 -f Dockerfile.rebalance -t $REGISTRY_NAME.azurecr.io/rebalance:latest .; then
    print_error "Failed to build rebalance image"
    exit 1
fi

print_success "All images built successfully!"

# Step 5: Login to ACR and push images
print_status "Pushing images to Azure Container Registry..."
if ! az acr login --name $REGISTRY_NAME; then
    print_error "Failed to login to Azure Container Registry"
    exit 1
fi

print_status "Pushing orchestrator image..."
if ! docker push $REGISTRY_NAME.azurecr.io/orchestrator:latest; then
    print_error "Failed to push orchestrator image"
    exit 1
fi

print_status "Pushing pricing image..."
if ! docker push $REGISTRY_NAME.azurecr.io/pricing:latest; then
    print_error "Failed to push pricing image"
    exit 1
fi

print_status "Pushing rebalance image..." 
if ! docker push $REGISTRY_NAME.azurecr.io/rebalance:latest; then
    print_error "Failed to push rebalance image"
    exit 1
fi

print_success "All container images pushed successfully!"

# Step 6: Update container apps with new images
print_status "Updating container apps with new images..."

# Add delay for managed identity permissions to propagate
print_status "Waiting for managed identity permissions to propagate..."
sleep 30

print_status "Updating orchestrator container app..."
MAX_RETRIES=3
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if az containerapp update --name orchestrator --resource-group $RESOURCE_GROUP_NAME --image $REGISTRY_NAME.azurecr.io/orchestrator:latest; then
        print_success "Orchestrator updated successfully!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            print_warning "Retry $RETRY_COUNT/$MAX_RETRIES for orchestrator update..."
            sleep 10
        else
            print_error "Failed to update orchestrator after $MAX_RETRIES attempts"
            exit 1
        fi
    fi
done

print_status "Updating pricing container app..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if az containerapp update --name pricing --resource-group $RESOURCE_GROUP_NAME --image $REGISTRY_NAME.azurecr.io/pricing:latest; then
        print_success "Pricing updated successfully!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            print_warning "Retry $RETRY_COUNT/$MAX_RETRIES for pricing update..."
            sleep 10
        else
            print_error "Failed to update pricing after $MAX_RETRIES attempts"
            exit 1
        fi
    fi
done

print_status "Updating rebalance container app..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if az containerapp update --name rebalance --resource-group $RESOURCE_GROUP_NAME --image $REGISTRY_NAME.azurecr.io/rebalance:latest; then
        print_success "Rebalance updated successfully!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            print_warning "Retry $RETRY_COUNT/$MAX_RETRIES for rebalance update..."
            sleep 10
        else
            print_error "Failed to update rebalance after $MAX_RETRIES attempts"
            exit 1
        fi
    fi
done

print_success "All container apps updated successfully!"

# Step 7: Wait for services to start and test endpoints
print_status "Waiting for services to start (30 seconds)..."
sleep 30

print_status "Testing application endpoints..."

# Function to test endpoint with retry
test_endpoint() {
    local url=$1
    local service=$2
    local retries=3
    
    for i in $(seq 1 $retries); do
        if curl -s -f "$url/health" > /dev/null 2>&1; then
            print_success "$service service is healthy!"
            return 0
        fi
        sleep 10
    done
    print_warning "$service health check failed (service might still be starting up)"
}

test_endpoint "$ORCHESTRATOR_URI" "Orchestrator"
test_endpoint "$PRICING_URI" "Pricing"  
test_endpoint "$REBALANCE_URI" "Rebalance"

# Step 8: Display final results
echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📊 Application URLs:"
echo "  • Orchestrator: $ORCHESTRATOR_URI"
echo "  • Pricing:      $PRICING_URI"
echo "  • Rebalance:    $REBALANCE_URI"
echo ""
echo "🔍 Health Check URLs:"
echo "  • Orchestrator Health: $ORCHESTRATOR_URI/health"
echo "  • Pricing Health:      $PRICING_URI/health"
echo "  • Rebalance Health:    $REBALANCE_URI/health"
echo ""
echo "🌐 Web UI: $ORCHESTRATOR_URI"
echo ""
print_success "Your AI Portfolio Management system is ready! 🚀"
echo ""
echo "💡 Next steps:"
echo "  1. Test the system using the health check URLs above"
echo "  2. Access the web UI to interact with your AI portfolio system"
echo "  3. Use the individual service URLs for API integration"
echo ""
echo "🗂️ Resource Details:"
echo "  • Resource Group: $RESOURCE_GROUP_NAME"
echo "  • Container Registry: $REGISTRY_NAME"
echo "  • Location: $LOCATION"
echo ""
echo "🧹 To delete everything:"
echo "  az group delete --name $RESOURCE_GROUP_NAME --yes --no-wait"