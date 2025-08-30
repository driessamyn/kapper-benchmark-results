#!/bin/bash
set -e

# List All Compute Instances Across Regions
# Shows status of all compute instances in all accessible regions

echo "📋 List All Compute Instances Across Regions"
echo "============================================="
echo ""

# Store original region
ORIGINAL_REGION=$(grep '^region=' ~/.oci/config | cut -d= -f2)
echo "🏠 Home region: $ORIGINAL_REGION"
echo ""

# Test all possible regions
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

TOTAL_INSTANCES=0
RUNNING_INSTANCES=0
STOPPED_INSTANCES=0
TERMINATED_INSTANCES=0
REGIONS_CHECKED=0

# Function to test region access
test_region_access() {
    local region=$1
    
    # Test access and get compartment ID using --region parameter
    local compartment_id
    if compartment_id=$(oci iam user list --region "$region" --query 'data[0]."compartment-id"' --raw-output 2>/dev/null); then
        if [ -n "$compartment_id" ] && [ "$compartment_id" != "null" ]; then
            echo "$compartment_id"
            return 0
        fi
    fi
    
    return 1
}

# Function to list instances in a region
list_instances_in_region() {
    local region=$1
    local compartment_id=$2
    
    # Get all instances (any state) using --region parameter
    local instances_json
    instances_json=$(oci compute instance list \
        --region "$region" \
        --compartment-id "$compartment_id" \
        --query 'data[*].{id:id,name:"display-name",shape:shape,state:"lifecycle-state",ad:"availability-domain",created:"time-created"}' \
        2>/dev/null)
    
    if [ -z "$instances_json" ] || [ "$instances_json" = "[]" ]; then
        return 0
    fi
    
    # Parse and display instances
    local instance_count
    instance_count=$(echo "$instances_json" | jq length)
    
    if [ "$instance_count" -gt 0 ]; then
        echo "   📦 Found $instance_count instance(s):"
        
        TOTAL_INSTANCES=$((TOTAL_INSTANCES + instance_count))
        
        # Process each instance
        local i=0
        while [ $i -lt "$instance_count" ]; do
            local instance_name
            local instance_shape
            local instance_state
            local instance_ad
            local instance_created
            local state_emoji
            
            instance_name=$(echo "$instances_json" | jq -r ".[$i].name")
            instance_shape=$(echo "$instances_json" | jq -r ".[$i].shape")
            instance_state=$(echo "$instances_json" | jq -r ".[$i].state")
            instance_ad=$(echo "$instances_json" | jq -r ".[$i].ad")
            instance_created=$(echo "$instances_json" | jq -r ".[$i].created")
            
            # Format creation date
            local created_date
            created_date=$(date -d "$instance_created" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "$instance_created")
            
            # Set emoji and count by state
            case "$instance_state" in
                "RUNNING")
                    state_emoji="🟢"
                    RUNNING_INSTANCES=$((RUNNING_INSTANCES + 1))
                    ;;
                "STOPPED")
                    state_emoji="🔴"
                    STOPPED_INSTANCES=$((STOPPED_INSTANCES + 1))
                    ;;
                "STOPPING")
                    state_emoji="🟡"
                    ;;
                "STARTING")
                    state_emoji="🟡"
                    ;;
                "TERMINATED")
                    state_emoji="⚫"
                    TERMINATED_INSTANCES=$((TERMINATED_INSTANCES + 1))
                    ;;
                "TERMINATING")
                    state_emoji="🟡"
                    ;;
                *)
                    state_emoji="❓"
                    ;;
            esac
            
            # Display instance info
            echo "      $state_emoji $instance_name"
            echo "         Shape: $instance_shape"
            echo "         State: $instance_state"
            echo "         AD: $instance_ad"
            echo "         Created: $created_date"
            
            # Show cost implications
            if [ "$instance_state" = "RUNNING" ]; then
                if [[ "$instance_shape" == "VM.Standard.A1.Flex"* ]]; then
                    echo "         💰 Cost: FREE (ARM A1 free tier)"
                elif [[ "$instance_shape" == "VM.Standard.E2.1.Micro"* ]]; then
                    echo "         💰 Cost: FREE (E2.1.Micro free tier)"
                else
                    echo "         💰 Cost: ⚠️  PAID INSTANCE - CHARGES APPLY!"
                fi
            elif [ "$instance_state" = "TERMINATED" ]; then
                echo "         💰 Cost: No charges (terminated)"
            else
                echo "         💰 Cost: No charges (stopped)"
            fi
            
            echo ""
            i=$((i + 1))
        done
    fi
}

# Scan each region
echo "🔍 Scanning all regions for compute instances..."
echo ""

for region in "${ALL_REGIONS[@]}"; do
    echo "🌐 Region: $region"
    
    if COMPARTMENT_ID=$(test_region_access "$region"); then
        echo "   ✅ Access confirmed"
        REGIONS_CHECKED=$((REGIONS_CHECKED + 1))
        list_instances_in_region "$region" "$COMPARTMENT_ID"
    else
        echo "   ❌ No access (not subscribed or no permissions)"
    fi
    
    echo ""
done

# No need to restore region since we used --region parameter

echo ""
echo "📊 Summary Report"
echo "=================="
echo "🌐 Regions checked: $REGIONS_CHECKED"
echo "📦 Total instances: $TOTAL_INSTANCES"
echo "🟢 Running instances: $RUNNING_INSTANCES"
echo "🔴 Stopped instances: $STOPPED_INSTANCES"
echo "⚫ Terminated instances: $TERMINATED_INSTANCES"

if [ $RUNNING_INSTANCES -gt 0 ]; then
    echo ""
    echo "⚠️  WARNING: You have $RUNNING_INSTANCES running instance(s)!"
    echo "   Running instances may incur charges."
    echo ""
    echo "💡 To stop all running instances:"
    echo "   ./setup/stop-all-instances.sh"
fi

if [ $TERMINATED_INSTANCES -gt 0 ]; then
    echo ""
    echo "ℹ️  NOTE: You have $TERMINATED_INSTANCES terminated instance(s)."
    echo "   Terminated instances are automatically removed by OCI."
    echo "   They will disappear from this list within 24-48 hours."
    echo ""
    echo "💡 To manually clean up terminated instances:"
    echo "   ./setup/stop-all-instances.sh --remove-terminated"
fi

if [ $TOTAL_INSTANCES -eq 0 ]; then
    echo ""
    echo "✅ No compute instances found in any accessible region."
    echo "💰 No compute charges expected."
fi

echo ""
echo "💡 Useful commands:"
echo "   ./setup/stop-all-instances.sh    # Stop all running instances"
echo "   ./setup/start-instance.sh        # Start specific instance"  
echo "   ./setup/delete-instance.sh       # Delete specific instance"