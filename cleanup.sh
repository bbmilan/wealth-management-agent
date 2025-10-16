#!/bin/bash
set -e

echo "🧹 Cleaning up AI Portfolio Management deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Configuration
ENVIRONMENT_NAME="dev"
LOCATION="uksouth"

# Generate user-specific suffix (same logic as deploy.sh)
USER_ID=$(az account show --query "user.name" -o tsv | md5sum | head -c 6 2>/dev/null || echo "$(whoami)" | md5sum | head -c 6)
RESOURCE_GROUP_NAME="rg-ai-${ENVIRONMENT_NAME}-${USER_ID}"

# Function to purge soft-deleted resources after deletion
purge_soft_deleted_resources() {
    print_status "Purging soft-deleted resources to prevent future conflicts..."
    
    # Calculate expected resource names based on Bicep logic (same as deploy.sh)
    local subscription_id=$(az account show --query "id" -o tsv)
    local resource_token=$(echo "${subscription_id}${RESOURCE_GROUP_NAME}${LOCATION}${ENVIRONMENT_NAME}" | md5sum | head -c 13)
    
    local vault_name="kv${resource_token}"
    local openai_name="ai${resource_token}"
    
    print_status "Purging Key Vault: $vault_name"
    az keyvault purge --name "$vault_name" --location "$LOCATION" 2>/dev/null && print_success "Key Vault purged" || print_warning "Key Vault not found in soft-delete (may have been purged already)"
    
    print_status "Purging Azure OpenAI: $openai_name"
    az cognitiveservices account purge --name "$openai_name" --resource-group "$RESOURCE_GROUP_NAME" --location "$LOCATION" 2>/dev/null && print_success "Azure OpenAI purged" || print_warning "Azure OpenAI not found in soft-delete (may have been purged already)"
    
    print_success "Soft-delete purging completed!"
}

# Check if resource group exists
EXISTING_RG=$(az group list --query "[?name=='${RESOURCE_GROUP_NAME}'].name" -o tsv 2>/dev/null || echo "")

if [ -z "$EXISTING_RG" ]; then
    print_warning "Resource group $RESOURCE_GROUP_NAME not found. Nothing to clean up."
    exit 0
fi

print_status "Found resource group: $RESOURCE_GROUP_NAME"

# List resources that will be deleted
print_status "Resources that will be deleted:"
az resource list --resource-group "$RESOURCE_GROUP_NAME" --query "[].{Name:name, Type:type}" -o table

echo ""
read -p "Are you sure you want to delete all resources in $RESOURCE_GROUP_NAME? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Cleanup cancelled."
    exit 0
fi

print_status "Deleting resource group: $RESOURCE_GROUP_NAME"
print_warning "This will delete all resources and cannot be undone!"

az group delete --name "$RESOURCE_GROUP_NAME" --yes --no-wait

print_success "Resource group deletion initiated!"
print_status "Waiting for deletion to complete before purging soft-deleted resources..."

# Wait for resource group deletion to complete
while az group show --name "$RESOURCE_GROUP_NAME" --query "properties.provisioningState" -o tsv 2>/dev/null | grep -q "Succeeded\|Failed"; do
    print_status "Resource group still exists, waiting 30 seconds..."
    sleep 30
done

print_success "Resource group deleted successfully!"

# Now purge soft-deleted resources
purge_soft_deleted_resources

echo ""
print_success "Complete cleanup finished! 🎉"
echo ""
print_status "All resources have been:"
print_status "  ✅ Deleted from resource group"  
print_status "  ✅ Purged from soft-delete state"
print_status "  ✅ Ready for fresh deployment"
echo ""
print_status "You can now run ./deploy.sh to create a new deployment."