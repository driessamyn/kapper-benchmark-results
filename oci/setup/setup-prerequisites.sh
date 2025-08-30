#!/bin/bash
set -e

# Setup Prerequisites for OCI Kapper Benchmarks
# One-time setup of persistent infrastructure that doesn't require cleanup

echo "🔧 OCI Kapper Benchmark Prerequisites Setup"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Check OCI CLI authentication
echo "🔐 Checking OCI CLI authentication..."
if ! oci iam user list --query 'data[0]."compartment-id"' --raw-output >/dev/null 2>&1; then
    echo "❌ OCI CLI not authenticated"
    echo "   Run: oci session authenticate"
    echo "   Or configure: oci setup config"
    exit 1
fi

COMPARTMENT_ID=$(oci iam user list --query 'data[0]."compartment-id"' --raw-output)
HOME_REGION=$(grep '^region=' ~/.oci/config | cut -d= -f2)
echo "✅ OCI CLI authenticated"
echo "   Home region: $HOME_REGION"
echo "   Compartment: ${COMPARTMENT_ID:0:50}..."
echo ""

# Setup SSH keys
echo "🔑 Setting up SSH keys..."
SSH_DIR="$HOME/.ssh"
SSH_KEY_PATH="$SSH_DIR/kapper-benchmark"

mkdir -p "$SSH_DIR"

if [ ! -f "${SSH_KEY_PATH}" ]; then
    echo "   Creating new SSH key pair..."
    ssh-keygen -t rsa -b 4096 -f "${SSH_KEY_PATH}" -N "" -C "kapper-benchmark-$(date +%Y%m%d)"
    echo "✅ SSH key created: ${SSH_KEY_PATH}"
else
    echo "✅ SSH key exists: ${SSH_KEY_PATH}"
fi

# Set proper permissions
chmod 600 "${SSH_KEY_PATH}"
chmod 644 "${SSH_KEY_PATH}.pub"
echo ""

# Get current public IP for SSH source restriction
echo "🌐 Getting current public IP for SSH restriction..."
PUBLIC_IP=$(curl -s --max-time 10 https://ipinfo.io/ip || curl -s --max-time 10 https://icanhazip.com || curl -s --max-time 10 https://ifconfig.me)

if [ -z "$PUBLIC_IP" ]; then
    echo "⚠️  Could not determine public IP - will use 0.0.0.0/0 (less secure)"
    SSH_SOURCE="0.0.0.0/0"
else
    echo "✅ Current public IP: $PUBLIC_IP"
    SSH_SOURCE="${PUBLIC_IP}/32"
    echo "🔒 SSH will be restricted to: $SSH_SOURCE"
fi
echo ""

# Function to setup network infrastructure in a region
setup_network_in_region() {
    local region=$1
    local compartment_id=$2
    
    echo "   📡 Setting up network infrastructure in $region..."
    
    # VCN
    VCN_NAME="kapper-benchmark-vcn-${region}"
    VCN_ID=$(oci network vcn list --region "$region" --compartment-id "$compartment_id" --display-name "$VCN_NAME" --query 'data[0].id' --raw-output 2>/dev/null)
    
    if [ "$VCN_ID" = "null" ] || [ -z "$VCN_ID" ]; then
        echo "   📡 Creating VCN..."
        VCN_RESULT=$(oci network vcn create \
            --region "$region" \
            --compartment-id "$compartment_id" \
            --display-name "$VCN_NAME" \
            --cidr-block "10.0.0.0/16" \
            --dns-label "kapperbench" \
            --wait-for-state AVAILABLE)
        VCN_ID=$(echo "$VCN_RESULT" | jq -r '.data.id')
        echo "   ✅ VCN created"
    else
        echo "   ✅ VCN exists"
    fi
    
    # Internet Gateway
    IG_NAME="kapper-benchmark-ig-${region}"
    IG_ID=$(oci network internet-gateway list --region "$region" --compartment-id "$compartment_id" --vcn-id "$VCN_ID" --display-name "$IG_NAME" --query 'data[0].id' --raw-output 2>/dev/null)
    
    if [ "$IG_ID" = "null" ] || [ -z "$IG_ID" ]; then
        echo "   🌐 Creating Internet Gateway..."
        IG_RESULT=$(oci network internet-gateway create \
            --region "$region" \
            --compartment-id "$compartment_id" \
            --vcn-id "$VCN_ID" \
            --display-name "$IG_NAME" \
            --is-enabled true \
            --wait-for-state AVAILABLE)
        IG_ID=$(echo "$IG_RESULT" | jq -r '.data.id')
        echo "   ✅ Internet Gateway created"
    else
        echo "   ✅ Internet Gateway exists"
    fi
    
    # Route Table
    RT_ID=$(oci network vcn get --region "$region" --vcn-id "$VCN_ID" --query 'data."default-route-table-id"' --raw-output)
    ROUTE_EXISTS=$(oci network route-table get --region "$region" --rt-id "$RT_ID" --query 'data."route-rules"[?destination==`0.0.0.0/0`]' --raw-output)
    
    if [ "$ROUTE_EXISTS" = "[]" ]; then
        echo "   🛣️  Adding internet route..."
        oci network route-table update --region "$region" --rt-id "$RT_ID" \
            --route-rules '[{"destination": "0.0.0.0/0", "networkEntityId": "'$IG_ID'"}]' \
            --force >/dev/null
        echo "   ✅ Internet route added"
    else
        echo "   ✅ Internet route exists"
    fi
    
    # Security List  
    SL_ID=$(oci network vcn get --region "$region" --vcn-id "$VCN_ID" --query 'data."default-security-list-id"' --raw-output)
    SSH_RULE_EXISTS=$(oci network security-list get --region "$region" --security-list-id "$SL_ID" --query "data.\"ingress-security-rules\"[?source==\`$SSH_SOURCE\` && protocol==\`6\` && \"tcp-options\".\"destination-port-range\".\"min\"==\`22\`]" --raw-output)
    
    if [ "$SSH_RULE_EXISTS" = "[]" ]; then
        echo "   🔒 Adding SSH security rule (source: $SSH_SOURCE)..."
        EXISTING_RULES=$(oci network security-list get --region "$region" --security-list-id "$SL_ID" --query 'data."ingress-security-rules"' --raw-output)
        NEW_RULES=$(echo "$EXISTING_RULES" | jq --arg source "$SSH_SOURCE" '. + [{"source": $source, "protocol": "6", "isStateless": false, "tcpOptions": {"destinationPortRange": {"min": 22, "max": 22}}}]')
        
        oci network security-list update --region "$region" --security-list-id "$SL_ID" \
            --ingress-security-rules "$NEW_RULES" \
            --force >/dev/null
        echo "   ✅ SSH security rule added"
    else
        echo "   ✅ SSH security rule exists"
    fi
    
    # Subnet
    SUBNET_NAME="kapper-benchmark-subnet-${region}"
    AD=$(oci iam availability-domain list --region "$region" --compartment-id "$compartment_id" --query 'data[0].name' --raw-output)
    SUBNET_ID=$(oci network subnet list --region "$region" --compartment-id "$compartment_id" --vcn-id "$VCN_ID" --display-name "$SUBNET_NAME" --query 'data[0].id' --raw-output 2>/dev/null)
    
    if [ "$SUBNET_ID" = "null" ] || [ -z "$SUBNET_ID" ]; then
        echo "   🏗️  Creating subnet..."
        SUBNET_RESULT=$(oci network subnet create \
            --region "$region" \
            --compartment-id "$compartment_id" \
            --vcn-id "$VCN_ID" \
            --display-name "$SUBNET_NAME" \
            --cidr-block "10.0.1.0/24" \
            --availability-domain "$AD" \
            --route-table-id "$RT_ID" \
            --security-list-ids '["'$SL_ID'"]' \
            --dns-label "kappersub" \
            --wait-for-state AVAILABLE)
        SUBNET_ID=$(echo "$SUBNET_RESULT" | jq -r '.data.id')
        echo "   ✅ Subnet created"
    else
        echo "   ✅ Subnet exists"
    fi
    
    # Save network configuration for this region
    cat > "instances/network-${region}.env" << EOF
# Network Configuration for $region
REGION=$region
VCN_ID=$VCN_ID
SUBNET_ID=$SUBNET_ID
INTERNET_GATEWAY_ID=$IG_ID
COMPARTMENT_ID=$compartment_id
SETUP_DATE="$(date)"
EOF
    
    echo "   💾 Network config saved: instances/network-${region}.env"
}

# Test regions for access and capacity
echo "🌐 Testing region access and setting up networks..."
REGIONS=(
    "us-phoenix-1"      # Good ARM availability
    "ca-toronto-1"      # Canada region  
    "uk-london-1"       # Home region
)

ACCESSIBLE_REGIONS=()
mkdir -p instances

for region in "${REGIONS[@]}"; do
    echo "🔍 Testing region: $region"
    
    # Test region access
    if region_compartment=$(oci iam user list --region "$region" --query 'data[0]."compartment-id"' --raw-output 2>/dev/null); then
        if [ -n "$region_compartment" ] && [ "$region_compartment" != "null" ]; then
            echo "   ✅ Access confirmed"
            ACCESSIBLE_REGIONS+=("$region")
            
            # Setup network infrastructure in this region
            setup_network_in_region "$region" "$region_compartment"
        else
            echo "   ❌ No access"
        fi
    else
        echo "   ❌ No access"
    fi
    echo ""
done

# Save prerequisites configuration
echo "💾 Saving prerequisites configuration..."
cat > "instances/prerequisites.env" << EOF
# Prerequisites configuration
ACCESSIBLE_REGIONS=(${ACCESSIBLE_REGIONS[*]})
SSH_KEY_PATH=$SSH_KEY_PATH
SSH_SOURCE=$SSH_SOURCE
HOME_REGION=$HOME_REGION
COMPARTMENT_ID=$COMPARTMENT_ID
SETUP_DATE="$(date)"
EOF

echo "✅ Prerequisites setup complete!"
echo ""
echo "📊 Summary:"
echo "   Accessible regions: ${#ACCESSIBLE_REGIONS[@]}"
echo "   Network infrastructure: Set up in all accessible regions"
echo "   SSH key: $SSH_KEY_PATH"
echo "   SSH access restricted to: $SSH_SOURCE"
echo ""
echo "🚀 Ready for benchmarks! Run:"
echo "   ./setup/run-benchmarks.sh <version>"
echo ""
echo "💡 The benchmark script will automatically find capacity and create instances"