#!/bin/bash

# ============================================
# Auto-update PostgreSQL Firewall with Current IP
# Run this periodically via cron to keep firewall updated
# ============================================

# Get current public IP
CURRENT_IP=$(curl -s https://api.ipify.org)

if [ -z "$CURRENT_IP" ]; then
    echo "❌ Error: Could not determine public IP address"
    exit 1
fi

echo "📡 Current public IP: $CURRENT_IP"

# Azure PostgreSQL settings
RESOURCE_GROUP="voice-agent-rg"
SERVER_NAME="seniorly-postgres-server"
RULE_NAME="AutoUpdatedIP"

# Check if rule exists
RULE_EXISTS=$(az postgres flexible-server firewall-rule show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --rule-name "$RULE_NAME" \
    --query "name" -o tsv 2>/dev/null)

if [ -z "$RULE_EXISTS" ]; then
    echo "📝 Creating new firewall rule..."
    az postgres flexible-server firewall-rule create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$SERVER_NAME" \
        --rule-name "$RULE_NAME" \
        --start-ip-address "$CURRENT_IP" \
        --end-ip-address "$CURRENT_IP" \
        --output none
    echo "✅ Firewall rule created for IP: $CURRENT_IP"
else
    # Get existing IP
    EXISTING_IP=$(az postgres flexible-server firewall-rule show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$SERVER_NAME" \
        --rule-name "$RULE_NAME" \
        --query "startIpAddress" -o tsv)

    if [ "$EXISTING_IP" = "$CURRENT_IP" ]; then
        echo "✅ IP unchanged: $CURRENT_IP (no update needed)"
    else
        echo "🔄 Updating firewall rule from $EXISTING_IP to $CURRENT_IP..."
        az postgres flexible-server firewall-rule update \
            --resource-group "$RESOURCE_GROUP" \
            --name "$SERVER_NAME" \
            --rule-name "$RULE_NAME" \
            --start-ip-address "$CURRENT_IP" \
            --end-ip-address "$CURRENT_IP" \
            --output none
        echo "✅ Firewall rule updated to: $CURRENT_IP"
    fi
fi

# Remove the old AllowMyIP and AllowAll rules if they exist
echo ""
echo "🧹 Cleaning up old firewall rules..."

az postgres flexible-server firewall-rule delete \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --rule-name "AllowMyIP" \
    --yes 2>/dev/null && echo "  Removed: AllowMyIP"

az postgres flexible-server firewall-rule delete \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --rule-name "AllowAll_2025-10-30_22-19-25" \
    --yes 2>/dev/null && echo "  Removed: AllowAll rule"

echo ""
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
echo "✅ PostgreSQL firewall updated successfully!"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
