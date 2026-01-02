#!/bin/bash
set -e

# Clean up orphaned block volumes that may be generating costs
# Run this periodically to ensure no volumes are left after instance termination

echo "🧹 Orphaned Volume Cleanup"
echo "=========================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Check prerequisites
if [ ! -f "instances/prerequisites.env" ]; then
    echo "❌ Prerequisites not found. Run: ./setup/setup-prerequisites.sh"
    exit 1
fi

source instances/prerequisites.env

echo "🔍 Scanning all regions for orphaned volumes..."
echo ""

TOTAL_ORPHANED=0
TOTAL_COST_ESTIMATE=0

for region in "${ACCESSIBLE_REGIONS[@]}"; do
    echo "🌐 Region: $region"
    
    # Find available volumes that might be orphaned
    VOLUMES=$(oci bv volume list \
        --region "$region" \
        --compartment-id "$COMPARTMENT_ID" \
        --lifecycle-state AVAILABLE \
        --query 'data[*].{id:"id", name:"display-name", size:"size-in-gbs", created:"time-created"}' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$VOLUMES" = "[]" ] || [ -z "$VOLUMES" ]; then
        echo "   ✅ No available volumes found"
    else
        VOLUME_COUNT=$(echo "$VOLUMES" | jq length)
        echo "   📋 Found $VOLUME_COUNT volume(s):"
        
        echo "$VOLUMES" | jq -r '.[] | "      📦 " + .name + " (" + (.size|tostring) + "GB, created: " + .created[0:10] + ")"'
        
        # Ask for confirmation before cleanup
        echo ""
        echo "   ⚠️  These volumes may be generating costs!"
        echo "   💰 Estimated daily cost per volume: ~$0.01-0.02 per 50GB"
        echo ""
        read -p "   Delete these volumes? [y/N]: " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "   🗑️  Deleting volumes..."
            
            echo "$VOLUMES" | jq -r '.[].id' | while read -r volume_id; do
                if [ -n "$volume_id" ]; then
                    echo "      Deleting: ${volume_id:0:20}..."
                    if oci bv volume delete \
                        --region "$region" \
                        --volume-id "$volume_id" \
                        --force >/dev/null 2>&1; then
                        echo "      ✅ Deleted successfully"
                        ((TOTAL_ORPHANED++))
                    else
                        echo "      ❌ Failed to delete"
                    fi
                fi
            done
        else
            echo "   ⏭️  Skipping deletion"
        fi
    fi
    echo ""
done

echo "📊 Cleanup Summary:"
echo "   🗑️  Volumes processed: $TOTAL_ORPHANED"
if [ $TOTAL_ORPHANED -gt 0 ]; then
    echo "   💰 Estimated cost savings: ~$0.01-0.02 per day"
else
    echo "   ✅ No cleanup needed"
fi
echo ""
echo "💡 To prevent future orphaned volumes:"
echo "   • Always use ./setup/stop-all-instances.sh when done"
echo "   • Use --quick mode for faster testing cycles"
echo "   • Run this script periodically to check for orphans"