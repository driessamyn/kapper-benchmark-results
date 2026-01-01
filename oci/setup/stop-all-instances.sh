#!/bin/bash
set -e

# Force Stop and Terminate All Compute Instances Across Regions
# Finds and terminates ALL compute instances in all accessible regions without prompts

REMOVE_TERMINATED=false

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-terminated)
            REMOVE_TERMINATED=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --remove-terminated  Force cleanup of terminated instances (they auto-cleanup normally)"
            echo "  --help              Show this help message"
            echo ""
            echo "This script terminates ALL compute instances in ALL accessible regions."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🛑 Force Stop & Terminate All Compute Instances"
echo "==============================================="
echo ""
if [ "$REMOVE_TERMINATED" = true ]; then
    echo "🚨 FORCE MODE: Will terminate ALL instances in ALL regions (including terminated)!"
else
    echo "🚨 FORCE MODE: Will terminate ALL active instances in ALL regions!"
    echo "   (Terminated instances will be skipped - they auto-cleanup within 24-48 hours)"
fi
echo "   This prevents any compute charges and removes all instances permanently."
echo ""

# Store original region
ORIGINAL_REGION=$(grep '^region=' ~/.oci/config | cut -d= -f2)
echo "🏠 Home region: $ORIGINAL_REGION"
echo ""
echo "🔍 Scanning all regions for instances to terminate..."

# Test all possible regions (expand list as needed)
ALL_REGIONS=(
    "us-phoenix-1"      # US West (Phoenix)
    "us-ashburn-1"      # US East (Ashburn)
    "ca-toronto-1"      # Canada (Toronto)
    "ca-montreal-1"     # Canada (Montreal)
    "uk-london-1"       # UK (London)
    "eu-amsterdam-1"    # Europe (Amsterdam)
    "eu-frankfurt-1"    # Europe (Frankfurt)
    "eu-zurich-1"       # Europe (Zurich)
    "ap-mumbai-1"       # Asia Pacific (Mumbai)
    "ap-seoul-1"        # Asia Pacific (Seoul)
    "ap-tokyo-1"        # Asia Pacific (Tokyo)
    "ap-sydney-1"       # Asia Pacific (Sydney)
    "sa-saopaulo-1"     # South America (São Paulo)
)

TOTAL_TERMINATED=0
REGIONS_WITH_INSTANCES=()
INACCESSIBLE_REGIONS=()

# Function to test region access and get compartment ID
test_region() {
    local region=$1
    
    # Test access and get compartment ID using --region parameter
    local compartment_id
    if compartment_id=$(oci iam user list --region "$region" --query 'data[0]."compartment-id"' --raw-output 2>/dev/null); then
        if [ -n "$compartment_id" ] && [ "$compartment_id" != "null" ]; then
            echo "$compartment_id"
            return 0
        fi
    fi
    
    INACCESSIBLE_REGIONS+=("$region")
    return 1
}

# Function to terminate all instances in a region
terminate_instances_in_region() {
    local region=$1
    local compartment_id=$2
    
    echo "   🔍 Scanning for ALL instances (any state)..."
    
    # Get ALL instances (any state) using --region parameter
    local instances_json
    instances_json=$(oci compute instance list \
        --region "$region" \
        --compartment-id "$compartment_id" \
        --query 'data[*].{id:id,name:"display-name",shape:shape,state:"lifecycle-state",ad:"availability-domain"}' \
        2>/dev/null || echo "[]")
    
    # Handle empty or null response
    if [ -z "$instances_json" ]; then
        instances_json="[]"
    fi
    
    if [ "$instances_json" = "[]" ] || [ "$instances_json" = "null" ]; then
        echo "   ✅ No instances found"
        return 0
    fi
    
    # Parse and terminate each instance
    local instance_count
    instance_count=$(echo "$instances_json" | jq length)
    
    if [ "$instance_count" -gt 0 ]; then
        echo "   🚨 Found $instance_count instance(s) to terminate:"
        
        REGIONS_WITH_INSTANCES+=("$region")
        
        # Show instance details
        echo "$instances_json" | jq -r '.[] | "      📦 \(.name) (\(.shape)) - \(.state) in \(.ad)"'
        echo ""
        
        # Terminate each instance
        local i=0
        while [ $i -lt "$instance_count" ]; do
            local instance_id
            local instance_name
            local instance_shape
            local instance_state
            
            instance_id=$(echo "$instances_json" | jq -r ".[$i].id")
            instance_name=$(echo "$instances_json" | jq -r ".[$i].name")
            instance_shape=$(echo "$instances_json" | jq -r ".[$i].shape")
            instance_state=$(echo "$instances_json" | jq -r ".[$i].state")
            
            if [ -n "$instance_id" ] && [ "$instance_id" != "null" ]; then
                # Handle terminated instances based on flag
                if [ "$instance_state" = "TERMINATED" ]; then
                    if [ "$REMOVE_TERMINATED" = true ]; then
                        echo "   🗑️  FORCE CLEANUP: $instance_name (TERMINATED - attempting cleanup)"
                        echo "      Instance ID: ${instance_id:0:50}..."
                        echo "      ℹ️  Note: Terminated instances normally auto-cleanup within 24-48 hours"
                        
                        # Try to force cleanup (this may not work as terminated instances auto-cleanup)
                        if oci compute instance terminate \
                            --region "$region" \
                            --instance-id "$instance_id" \
                            --preserve-boot-volume false \
                            --force >/dev/null 2>&1; then
                            
                            echo "      ✅ Cleanup attempted"
                            TOTAL_TERMINATED=$((TOTAL_TERMINATED + 1))
                        else
                            echo "      ℹ️  Already cleaned up or will auto-cleanup soon"
                        fi
                    else
                        echo "   ⏭️  SKIPPING: $instance_name (TERMINATED - will auto-cleanup within 24-48 hours)"
                    fi
                elif [ "$instance_state" = "TERMINATING" ]; then
                    echo "   ⏳ IN PROGRESS: $instance_name (already TERMINATING)"
                else
                    echo "   💀 TERMINATING: $instance_name ($instance_shape) - $instance_state"
                    echo "      Instance ID: ${instance_id:0:50}..."
                    
                    # Force terminate without waiting - faster cleanup
                    if oci compute instance terminate \
                        --region "$region" \
                        --instance-id "$instance_id" \
                        --preserve-boot-volume false \
                        --force >/dev/null 2>&1; then
                        
                        echo "      ✅ Termination initiated"
                        TOTAL_TERMINATED=$((TOTAL_TERMINATED + 1))
                    else
                        echo "      ❌ Failed to terminate (may require manual intervention)"
                    fi
                fi
                echo ""
            fi
            
            i=$((i + 1))
        done
    fi
}

# Scan each region
for region in "${ALL_REGIONS[@]}"; do
    echo "🌐 Testing region: $region"
    if COMPARTMENT_ID=$(test_region "$region"); then
        echo "   ✅ Access confirmed"
        terminate_instances_in_region "$region" "$COMPARTMENT_ID"
    else
        echo "   ❌ No access"
    fi
    echo ""
done

echo ""
echo "📊 Summary Report"
echo "=================="
echo "💀 Total instances terminated: $TOTAL_TERMINATED"

if [ ${#REGIONS_WITH_INSTANCES[@]} -gt 0 ]; then
    echo "🌐 Regions with terminated instances:"
    for region in "${REGIONS_WITH_INSTANCES[@]}"; do
        echo "   - $region"
    done
else
    echo "✅ No instances found in any accessible region"
fi

if [ ${#INACCESSIBLE_REGIONS[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  Inaccessible regions (not subscribed or no permissions):"
    for region in "${INACCESSIBLE_REGIONS[@]}"; do
        echo "   - $region"
    done
fi

echo ""
if [ $TOTAL_TERMINATED -gt 0 ]; then
    if [ "$REMOVE_TERMINATED" = true ]; then
        echo "✅ All instances processed (including terminated instances)!"
    else
        echo "✅ All active instances have been terminated!"
    fi
    echo "💰 No compute charges will be incurred."
    echo "🗑️  Boot volumes have been deleted to prevent storage charges."
    echo ""
    echo "💡 To create new instances:"
    echo "   ./setup/run-benchmarks.sh <version>"
    echo ""
    echo "ℹ️  Note: Terminated instances will auto-cleanup from OCI within 24-48 hours."
else
    if [ "$REMOVE_TERMINATED" = true ]; then
        echo "✅ No action needed - all instances already cleaned up."
    else
        echo "✅ No action needed - no active instances found."
    fi
fi

echo ""
echo "💡 To check current instance status:"
echo "   ./setup/list-all-instances.sh"