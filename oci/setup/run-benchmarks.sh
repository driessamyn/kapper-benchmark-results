#!/bin/bash
set -e

# Run Kapper Benchmarks on OCI
# Complete benchmark execution: create → deploy → run → download → cleanup

# Check for help first
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 <version> [options]"
    echo ""
    echo "Options:"
    echo "  --baseline <version> Specify baseline version for comparison analysis"
    echo "  --quick              Use quick benchmark mode (faster, less accurate)"
    echo "  --keep-instance      Don't terminate instance after completion"
    echo "  --force-new-instance Force creation of new instance (bypass reuse)"
    echo ""
    echo "Examples:"
    echo "  $0 1.6.1"
    echo "  $0 1.6.1 --quick"
    echo "  $0 1.6.1 --baseline 1.5.0"
    echo "  $0 1.6.1 --baseline 1.5.0 --quick"
    echo "  $0 1.6.1 --keep-instance"
    echo "  $0 1.6.1 --force-new-instance"
    echo ""
    echo "Instance Reuse:"
    echo "  By default, the script will reuse existing instances in the selected region"
    echo "  for faster testing. Use --force-new-instance to always create new instances."
    exit 0
fi

if [ $# -eq 0 ]; then
    echo "Usage: $0 <version> [options]"
    echo "Run: $0 --help for detailed usage information"
    exit 1
fi

VERSION="$1"
shift

# Parse options
QUICK_MODE=false
KEEP_INSTANCE=false
FORCE_NEW_INSTANCE=false
BASELINE_VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --baseline)
            if [ -z "$2" ]; then
                echo "❌ Error: --baseline requires a version argument"
                exit 1
            fi
            BASELINE_VERSION="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --keep-instance)
            KEEP_INSTANCE=true
            shift
            ;;
        --force-new-instance)
            FORCE_NEW_INSTANCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Kapper Benchmark Run - Version $VERSION"
echo "========================================"
if [ -n "$BASELINE_VERSION" ]; then
    echo "📊 Baseline comparison: $BASELINE_VERSION → $VERSION"
else
    echo "📊 Single version benchmark (no baseline comparison)"
fi
echo ""

# Validate baseline if specified
if [ -n "$BASELINE_VERSION" ]; then
    echo "🔍 Validating baseline version $BASELINE_VERSION..."
    
    # Check if baseline results exist locally
    if [ ! -d "../results/$BASELINE_VERSION" ]; then
        echo "❌ Baseline results not found locally: results/$BASELINE_VERSION"
        echo "   Please run benchmarks for $BASELINE_VERSION first, or"
        echo "   ensure the baseline results directory exists locally"
        exit 1
    fi
    
    # Check for essential baseline files
    BASELINE_FILES_MISSING=false
    for file in "info.txt" "main-results-avgt.json"; do
        if [ ! -f "../results/$BASELINE_VERSION/$file" ]; then
            echo "❌ Missing baseline file: results/$BASELINE_VERSION/$file"
            BASELINE_FILES_MISSING=true
        fi
    done
    
    if [ "$BASELINE_FILES_MISSING" = true ]; then
        echo "❌ Baseline results incomplete. Please run complete benchmarks for $BASELINE_VERSION first."
        exit 1
    fi
    
    echo "✅ Baseline validation passed: $BASELINE_VERSION"
    echo ""
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Check prerequisites
echo "🔍 Checking prerequisites..."
if [ ! -f "instances/prerequisites.env" ]; then
    echo "❌ Prerequisites not set up"
    echo "   Run: ./setup/setup-prerequisites.sh"
    exit 1
fi

source instances/prerequisites.env

if [ ${#ACCESSIBLE_REGIONS[@]} -eq 0 ]; then
    echo "❌ No accessible regions found"
    echo "   Run: ./setup/setup-prerequisites.sh"
    exit 1
fi

echo "✅ Prerequisites ready"
echo "   Accessible regions: ${ACCESSIBLE_REGIONS[*]}"
echo ""

# Find capacity across accessible regions
echo "🔍 Finding ARM A1 capacity across regions..."
SELECTED_REGION=""
SELECTED_CONFIG=""

for region in "${ACCESSIBLE_REGIONS[@]}"; do
    echo "⚡ Testing capacity in: $region"
    
    # Load network config
    if [ -f "instances/network-${region}.env" ]; then
        source "instances/network-${region}.env"
        
        # Get Oracle Linux Cloud Developer image (has JDK pre-installed)
        IMAGE_ID=$(oci compute image list \
            --region "$region" \
            --compartment-id "$COMPARTMENT_ID" \
            --query 'data[?contains("display-name", `Oracle-Linux-Cloud-Developer`) && contains("display-name", `aarch64`)].id | [0]' \
            --raw-output 2>/dev/null || echo "")
        
        if [ -n "$IMAGE_ID" ] && [ "$IMAGE_ID" != "null" ]; then
            echo "   ✅ Oracle Linux Cloud Developer image available"
            
            # Test capacity by trying to create the actual instance we need
            ADS_RAW=$(oci iam availability-domain list --region "$region" --compartment-id "$COMPARTMENT_ID" --query 'data[*].name' --raw-output 2>/dev/null)
            
            # Parse availability domains  
            ADS=()
            while IFS= read -r line; do
                if [[ "$line" =~ \"([^\"]+)\" ]]; then
                    ADS+=("${BASH_REMATCH[1]}")
                fi
            done <<< "$ADS_RAW"
            
            # We found a usable region, save it and continue with instance creation
            if [ ${#ADS[@]} -gt 0 ]; then
                echo "   🎯 Will use region: $region"
                SELECTED_REGION="$region"
                SELECTED_CONFIG="instances/network-${region}.env"
                break
            fi
        else
            echo "   ❌ No Oracle Linux Cloud Developer image found"
        fi
    else
        echo "   ❌ Network config missing"
    fi
done

if [ -z "$SELECTED_REGION" ]; then
    echo ""
    echo "😞 No suitable regions found"
    echo "   Check that prerequisites are set up correctly"
    echo "   Run: ./setup/setup-prerequisites.sh"
    exit 1
fi

echo "🎯 Selected region: $SELECTED_REGION"

# Reload the selected region's configuration
source "$SELECTED_CONFIG"
echo "✅ Network configuration loaded for $SELECTED_REGION"
echo ""

# Check for running instances in selected region
REUSE_INSTANCE=false
EXISTING_INSTANCE_OCID=""
EXISTING_PUBLIC_IP=""
EXISTING_PRIVATE_IP=""

if [ "$FORCE_NEW_INSTANCE" = false ]; then
    echo "🔄 Checking for running instances in $SELECTED_REGION..."
else
    echo "🆕 Force new instance requested - checking for existing instances to terminate..."
    
    # Get all running instances with our naming pattern for cleanup
    RUNNING_INSTANCES_RAW=$(oci compute instance list \
        --region "$SELECTED_REGION" \
        --compartment-id "$COMPARTMENT_ID" \
        --query 'data[?("lifecycle-state" == `RUNNING`) && contains("display-name", `kapper-benchmark`)].id' \
        --raw-output 2>/dev/null || echo "[]")
    
    if [ "$RUNNING_INSTANCES_RAW" != "[]" ] && [ -n "$RUNNING_INSTANCES_RAW" ]; then
        RUNNING_INSTANCES=$(echo "$RUNNING_INSTANCES_RAW" | jq -r '.[]' 2>/dev/null || echo "")
        
        if [ -n "$RUNNING_INSTANCES" ]; then
            INSTANCE_ARRAY=()
            while IFS= read -r line; do
                if [ -n "$line" ]; then
                    INSTANCE_ARRAY+=("$line")
                fi
            done <<< "$RUNNING_INSTANCES"
            
            INSTANCE_COUNT=${#INSTANCE_ARRAY[@]}
            
            if [ $INSTANCE_COUNT -gt 0 ]; then
                echo "   Found $INSTANCE_COUNT existing benchmark instance(s) - terminating for clean slate..."
                
                for instance_id in "${INSTANCE_ARRAY[@]}"; do
                    echo "   🗑️  Terminating instance: $instance_id"
                    oci compute instance terminate \
                        --region "$SELECTED_REGION" \
                        --instance-id "$instance_id" \
                        --preserve-boot-volume false \
                        --force >/dev/null 2>&1 || echo "   ⚠️  Failed to terminate $instance_id"
                done
                
                echo "   ✅ Existing instances terminated - proceeding with fresh instance"
            fi
        fi
    else
        echo "   ✅ No existing instances found - proceeding with fresh instance"
    fi
fi

if [ "$FORCE_NEW_INSTANCE" = false ]; then
    echo "🔄 Checking for running instances in $SELECTED_REGION..."
    
    # Get all running instances with our naming pattern
    RUNNING_INSTANCES_RAW=$(oci compute instance list \
        --region "$SELECTED_REGION" \
        --compartment-id "$COMPARTMENT_ID" \
        --query 'data[?("lifecycle-state" == `RUNNING`) && contains("display-name", `kapper-benchmark`)].id' \
        --raw-output 2>/dev/null || echo "[]")
    
    # Check if we have actual instances (not just empty array)
    if [ "$RUNNING_INSTANCES_RAW" != "[]" ] && [ -n "$RUNNING_INSTANCES_RAW" ]; then
        # Parse the JSON array to get individual instance IDs
        RUNNING_INSTANCES=$(echo "$RUNNING_INSTANCES_RAW" | jq -r '.[]' 2>/dev/null || echo "")
        
        if [ -n "$RUNNING_INSTANCES" ]; then
            # Convert to array for proper counting
            INSTANCE_ARRAY=()
            while IFS= read -r line; do
                if [ -n "$line" ]; then
                    INSTANCE_ARRAY+=("$line")
                fi
            done <<< "$RUNNING_INSTANCES"
            
            INSTANCE_COUNT=${#INSTANCE_ARRAY[@]}
            echo "   📋 Found $INSTANCE_COUNT running kapper-benchmark instance(s)"
            
            if [ "$INSTANCE_COUNT" -gt 1 ]; then
            echo "   🗑️  Multiple instances detected - terminating all instances..."
            for instance_id in "${INSTANCE_ARRAY[@]}"; do
                echo "      Terminating: ${instance_id:0:50}..."
                oci compute instance terminate \
                    --region "$SELECTED_REGION" \
                    --instance-id "$instance_id" \
                    --preserve-boot-volume false \
                    --force >/dev/null 2>&1 || true
            done
            echo "   ⏳ Waiting for terminations to complete..."
            sleep 15  # Give time for terminations to process
            echo "   ✅ All instances terminated - will create new instance"
        elif [ "$INSTANCE_COUNT" -eq 1 ]; then
            # Single instance found - try to reuse it
            CANDIDATE_INSTANCE="${INSTANCE_ARRAY[0]}"
            echo "   🔍 Testing SSH connectivity to: ${CANDIDATE_INSTANCE:0:50}..."
            
            # Get instance IP addresses
            VNIC_ATTACHMENT=$(oci compute vnic-attachment list \
                --region "$SELECTED_REGION" \
                --compartment-id "$COMPARTMENT_ID" \
                --instance-id "$CANDIDATE_INSTANCE" \
                --query 'data[0]."vnic-id"' \
                --raw-output 2>/dev/null)
            
            if [ -n "$VNIC_ATTACHMENT" ] && [ "$VNIC_ATTACHMENT" != "null" ]; then
                VNIC_INFO=$(oci network vnic get --region "$SELECTED_REGION" --vnic-id "$VNIC_ATTACHMENT" 2>/dev/null)
                CANDIDATE_PUBLIC_IP=$(echo "$VNIC_INFO" | jq -r '.data."public-ip"' 2>/dev/null || echo "")
                CANDIDATE_PRIVATE_IP=$(echo "$VNIC_INFO" | jq -r '.data."private-ip"' 2>/dev/null || echo "")
                
                if [ -n "$CANDIDATE_PUBLIC_IP" ] && [ "$CANDIDATE_PUBLIC_IP" != "null" ]; then
                    echo "      Testing SSH to: $CANDIDATE_PUBLIC_IP"
                    
                    # Remove any conflicting SSH keys
                    ssh-keygen -R "$CANDIDATE_PUBLIC_IP" 2>/dev/null || true
                    
                    # Test SSH connectivity with multiple attempts and longer timeout
                    SSH_SUCCESS=false
                    for ssh_attempt in {1..3}; do
                        echo "        SSH attempt $ssh_attempt/3..."
                        # First try: Check if cloud-init is complete (ideal for fresh instances)
                        if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=5 \
                            benchmark@"$CANDIDATE_PUBLIC_IP" "echo 'SSH test successful' && test -f ~/.cloud-init-complete" >/dev/null 2>&1; then
                            echo "        ✅ SSH successful and cloud-init complete"
                            SSH_SUCCESS=true
                            break
                        fi
                        # Fallback: Just test basic SSH (for instances that have been running)
                        if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=5 \
                            benchmark@"$CANDIDATE_PUBLIC_IP" "echo 'SSH test successful'" >/dev/null 2>&1; then
                            echo "        ✅ SSH successful (cloud-init status unknown but SSH works)"
                            SSH_SUCCESS=true
                            break
                        fi
                        if [ $ssh_attempt -lt 3 ]; then
                            echo "        ❌ SSH failed, waiting 15 seconds before retry..."
                            sleep 15
                        fi
                    done
                    
                    if [ "$SSH_SUCCESS" = true ]; then
                        
                        echo "   ✅ SSH successful - reusing instance:"
                        echo "      Instance ID: ${CANDIDATE_INSTANCE:0:50}..."
                        echo "      Public IP: $CANDIDATE_PUBLIC_IP"
                        
                        REUSE_INSTANCE=true
                        EXISTING_INSTANCE_OCID="$CANDIDATE_INSTANCE"
                        EXISTING_PUBLIC_IP="$CANDIDATE_PUBLIC_IP"
                        EXISTING_PRIVATE_IP="$CANDIDATE_PRIVATE_IP"
                    else
                        echo "   ❌ SSH failed after 3 attempts - checking instance details..."
                        # Get more details about why SSH might be failing
                        INSTANCE_STATE=$(oci compute instance get --region "$SELECTED_REGION" --instance-id "$CANDIDATE_INSTANCE" --query 'data."lifecycle-state"' --raw-output 2>/dev/null || echo "UNKNOWN")
                        echo "      Instance state: $INSTANCE_STATE"
                        
                        # Try a final diagnostic SSH attempt with verbose output
                        echo "      Final diagnostic attempt (showing errors):"
                        ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
                            benchmark@"$CANDIDATE_PUBLIC_IP" "echo 'SSH diagnostic test'" 2>&1 || true
                        
                        echo "   🗑️ Terminating problematic instance..."
                        oci compute instance terminate \
                            --region "$SELECTED_REGION" \
                            --instance-id "$CANDIDATE_INSTANCE" \
                            --preserve-boot-volume false \
                            --force >/dev/null 2>&1 || true
                        echo "   ⏳ Waiting for termination to complete..."
                        sleep 10
                        echo "   ✅ Problematic instance terminated - will create new instance"
                    fi
                else
                    echo "   ❌ Could not get IP address - terminating instance..."
                    oci compute instance terminate \
                        --region "$SELECTED_REGION" \
                        --instance-id "$CANDIDATE_INSTANCE" \
                        --preserve-boot-volume false \
                        --force >/dev/null 2>&1 || true
                    echo "   ⏳ Waiting for termination to complete..."
                    sleep 10
                    echo "   ✅ Instance terminated - will create new instance"
                fi
            else
                echo "   ❌ Could not get network info - terminating instance..."
                oci compute instance terminate \
                    --region "$SELECTED_REGION" \
                    --instance-id "$CANDIDATE_INSTANCE" \
                    --preserve-boot-volume false \
                    --force >/dev/null 2>&1 || true
                echo "   ⏳ Waiting for termination to complete..."
                sleep 10
                echo "   ✅ Instance terminated - will create new instance"
            fi
            fi  # Close the elif condition
        else
            echo "   📝 No valid running kapper-benchmark instances found"
        fi
    else
        echo "   📝 No running kapper-benchmark instances found"
    fi
else
    echo "🆕 Force new instance mode - skipping reuse check"
fi
echo ""

# Create results directory
RESULTS_DIR="../results/$VERSION"
mkdir -p "$RESULTS_DIR"
echo "📁 Results directory: $RESULTS_DIR"

# Oracle Linux Cloud Developer image was already found during capacity checking
echo "✅ Oracle Linux Cloud Developer image: ${IMAGE_ID:0:50}..."
echo ""

# Set up instance variables
if [ "$REUSE_INSTANCE" = true ]; then
    # Use existing instance
    INSTANCE_OCID="$EXISTING_INSTANCE_OCID"
    PUBLIC_IP="$EXISTING_PUBLIC_IP"
    PRIVATE_IP="$EXISTING_PRIVATE_IP"
    REGION="$SELECTED_REGION"
    INSTANCE_NAME="reused-instance"
    
    echo "⏩ Skipping instance creation - using existing instance"
else
    # Create new instance
    echo "🆕 Creating new instance..."

    # Create cloud-init script
    echo "☁️  Preparing cloud-init script..."
    cat > /tmp/cloud-init.yaml << 'EOF'
#cloud-config
package_update: true
# Oracle Linux Cloud Developer already has JDK - install utilities and attempt Docker
packages:
  - unzip
  - htop
  - git

# Setup for Oracle Linux - minimal cloud-init (Docker handled at runtime for reliability)
runcmd:
  # Basic system setup only - use pre-installed Python 3.11 on Oracle Linux Cloud Developer
  - dnf update -y
  # Install Python 3.11 pip (Python 3.11 is pre-installed)
  - dnf install -y python3.11-pip
  # Set up Python 3.11 symlinks for compatibility
  - ln -sf /usr/bin/python3.11 /usr/local/bin/python3
  - ln -sf /usr/bin/pip3.11 /usr/local/bin/pip3
  # Fix home directory ownership
  - chown -R benchmark:benchmark /home/benchmark
  - chmod 755 /home/benchmark
  # Signal that cloud-init is complete
  - echo "Cloud-init complete" > /home/benchmark/setup.log
  - chown benchmark:benchmark /home/benchmark/setup.log
  - sudo -u benchmark touch /home/benchmark/.cloud-init-complete

# Create benchmark user
users:
  - name: benchmark
    groups: wheel
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - PLACEHOLDER_SSH_KEY

write_files:
  - path: /home/benchmark/.bashrc
    content: |
      alias ll='ls -la'
    owner: benchmark:benchmark
    permissions: '0644'

final_message: "Kapper benchmark instance ready!"
EOF

# Replace SSH key placeholder
SSH_PUBLIC_KEY=$(cat "${SSH_KEY_PATH}.pub")
sed -i '' "s|PLACEHOLDER_SSH_KEY|$SSH_PUBLIC_KEY|" /tmp/cloud-init.yaml
echo "✅ Cloud-init script prepared"
echo ""

# Create compute instance
echo "🏗️  Creating compute instance..."
INSTANCE_NAME="kapper-benchmark-${VERSION}-$(date +%Y%m%d-%H%M%S)"

# Get availability domains and try each one
ADS_RAW=$(oci iam availability-domain list --region "$SELECTED_REGION" --compartment-id "$COMPARTMENT_ID" --query 'data[*].name' --raw-output)

ADS=()
while IFS= read -r line; do
    if [[ "$line" =~ \"([^\"]+)\" ]]; then
        ADS+=("${BASH_REMATCH[1]}")
    fi
done <<< "$ADS_RAW"

INSTANCE_OCID=""
for AD in "${ADS[@]}"; do
    echo "   Trying availability domain: $AD"
    
    if INSTANCE_OCID=$(oci compute instance launch \
        --region "$SELECTED_REGION" \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AD" \
        --subnet-id "$SUBNET_ID" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config '{"ocpus": 4, "memoryInGBs": 24}' \
        --image-id "$IMAGE_ID" \
        --display-name "$INSTANCE_NAME" \
        --ssh-authorized-keys-file "${SSH_KEY_PATH}.pub" \
        --user-data-file /tmp/cloud-init.yaml \
        --assign-public-ip true \
        --wait-for-state RUNNING \
        --query 'data.id' \
        --raw-output 2>/dev/null); then
        
        echo "   ✅ Success in $AD!"
        break
    else
        echo "   ❌ Failed in $AD"
    fi
done

    if [ -z "$INSTANCE_OCID" ]; then
        echo ""
        echo "❌ Failed to create instance in $SELECTED_REGION"
        echo "   ARM capacity may have been consumed"
        echo "   Try again or run: ./setup/setup-prerequisites.sh"
        rm -f /tmp/cloud-init.yaml
        exit 1
    fi

    echo "✅ Instance created: ${INSTANCE_OCID:0:50}..."
    rm -f /tmp/cloud-init.yaml

    # Get instance details
    echo "📋 Getting instance details..."
    
    # Get VNIC attachment for reliable IP address retrieval
    VNIC_ATTACHMENT=$(oci compute vnic-attachment list --region "$SELECTED_REGION" --compartment-id "$COMPARTMENT_ID" --instance-id "$INSTANCE_OCID" --query 'data[0]."vnic-id"' --raw-output)
    
    if [ -n "$VNIC_ATTACHMENT" ] && [ "$VNIC_ATTACHMENT" != "null" ]; then
        echo "   📡 Getting VNIC details..."
        VNIC_INFO=$(oci network vnic get --region "$SELECTED_REGION" --vnic-id "$VNIC_ATTACHMENT")
        PUBLIC_IP=$(echo "$VNIC_INFO" | jq -r '.data."public-ip"')
        PRIVATE_IP=$(echo "$VNIC_INFO" | jq -r '.data."private-ip"')
    else
        # Fallback to instance data (less reliable)
        INSTANCE_INFO=$(oci compute instance get --region "$SELECTED_REGION" --instance-id "$INSTANCE_OCID")
        PUBLIC_IP=$(echo "$INSTANCE_INFO" | jq -r '.data."primary-public-ip"')
        PRIVATE_IP=$(echo "$INSTANCE_INFO" | jq -r '.data."primary-private-ip"')
    fi
    
    REGION="$SELECTED_REGION"

    echo "✅ Instance ready:"
    echo "   Instance ID: ${INSTANCE_OCID:0:50}..."  
    echo "   Public IP: $PUBLIC_IP"
    echo "   Private IP: $PRIVATE_IP"
    echo ""
fi

# Wait for SSH to be ready
echo "⏳ Waiting for SSH access..."

# For reused instances, SSH should be ready immediately  
if [ "$REUSE_INSTANCE" = true ]; then
    echo "   ✅ SSH already tested during reuse check - skipping wait"
    SSH_READY=true
else
    echo "   🕐 Waiting extra time for cloud-init to complete..."
    sleep 30  # Give cloud-init more time to complete
    SSH_READY=false
fi

# Test SSH connectivity with longer timeout (skip if already ready)
if [ "$SSH_READY" != true ]; then
    for i in {1..90}; do
        if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=10 benchmark@$PUBLIC_IP "echo 'SSH ready'" >/dev/null 2>&1; then
            echo "✅ SSH access ready"
            SSH_READY=true
            
            # Check if cloud-init is complete
            if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "test -f ~/.cloud-init-complete" >/dev/null 2>&1; then
                echo "✅ Cloud-init setup complete"
            else
                echo "⏳ SSH ready, waiting for cloud-init to complete..."
                echo "   Note: Docker installation can take 5-10 minutes..."
                
                # Check if cloud-init has failed early
                CLOUD_INIT_STATUS=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "cloud-init status" 2>/dev/null || echo "unknown")
                if [[ "$CLOUD_INIT_STATUS" == *"error"* ]]; then
                    echo "⚠️  Cloud-init failed, attempting manual environment setup..."
                    echo "   Cloud-init status: $CLOUD_INIT_STATUS"
                    
                    # Manual environment setup when cloud-init fails
                    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP << 'MANUAL_SETUP'
echo "=== Manual Environment Setup ==="
# Fix home directory permissions
sudo chown -R benchmark:benchmark /home/benchmark
sudo chmod 755 /home/benchmark

# Set up Python 3.11 (Oracle Linux Cloud Developer has it pre-installed)
if command -v python3.11 >/dev/null 2>&1; then
    echo "Setting up Python 3.11..."
    sudo dnf install -y python3.11-pip >/dev/null 2>&1 || true
    sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3
    sudo ln -sf /usr/bin/pip3.11 /usr/local/bin/pip3
    echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc
else
    echo "Python 3.11 not found, using system Python"
fi

# Test Python
/usr/local/bin/python3 --version 2>/dev/null || python3 --version

# Test container runtime (Podman with Docker compatibility is pre-installed)
if command -v podman >/dev/null 2>&1; then
    echo "Podman available for container runtime"
    podman --version
elif command -v docker >/dev/null 2>&1; then
    echo "Docker available for container runtime"
    docker --version
else
    echo "Warning: No container runtime found"
fi

# Mark setup as complete
touch ~/.cloud-init-complete
echo "$(date): Manual environment setup complete" >> ~/setup.log
echo "=== Manual Setup Complete ==="
MANUAL_SETUP
                    
                    if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "test -f ~/.cloud-init-complete" >/dev/null 2>&1; then
                        echo "✅ Manual environment setup successful"
                    else
                        echo "❌ Manual environment setup failed"
                        exit 1
                    fi
                else
                    # Wait for normal cloud-init completion (reduced timeout)
                    for j in {1..20}; do
                        if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "test -f ~/.cloud-init-complete" >/dev/null 2>&1; then
                            echo "✅ Cloud-init setup complete"
                            break
                        fi
                        
                        # Show progress every 30 seconds
                        if [ $((j % 3)) -eq 0 ]; then
                            echo "   Still waiting for cloud-init... (${j}0 seconds elapsed)"
                            # Show cloud-init status for debugging
                            CLOUD_INIT_STATUS=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "cloud-init status" 2>/dev/null || echo "unknown")
                            echo "   Cloud-init status: $CLOUD_INIT_STATUS"
                            
                            # If cloud-init shows error status, switch to manual setup
                            if [[ "$CLOUD_INIT_STATUS" == *"error"* ]]; then
                                echo "⚠️  Cloud-init error detected, switching to manual setup..."
                                break
                            fi
                        fi
                        
                        if [ $j -eq 20 ]; then
                            echo "⚠️  Cloud-init timeout (6+ minutes), attempting manual setup..."
                        fi
                        sleep 10
                    done
                    
                    # If we still don't have completion marker, try manual setup
                    if ! ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "test -f ~/.cloud-init-complete" >/dev/null 2>&1; then
                        echo "🔧 Cloud-init incomplete, running manual environment setup..."
                        # Run the same manual setup as above
                        ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP << 'MANUAL_SETUP_FALLBACK'
echo "=== Fallback Manual Environment Setup ==="
sudo chown -R benchmark:benchmark /home/benchmark 2>/dev/null || true
sudo chmod 755 /home/benchmark 2>/dev/null || true
if command -v python3.11 >/dev/null 2>&1; then
    sudo dnf install -y python3.11-pip >/dev/null 2>&1 || true
    sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3 2>/dev/null || true
    sudo ln -sf /usr/bin/pip3.11 /usr/local/bin/pip3 2>/dev/null || true
    echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc 2>/dev/null || true
fi
touch ~/.cloud-init-complete 2>/dev/null || true
echo "$(date): Fallback setup complete" >> ~/setup.log 2>/dev/null || true
echo "=== Fallback Setup Complete ==="
MANUAL_SETUP_FALLBACK
                        echo "✅ Manual environment setup completed"
                    fi
                fi
            fi
            break
        fi
        if [ $i -eq 90 ]; then
            echo "❌ SSH timeout after 15 minutes"
            echo "   Instance ID: ${INSTANCE_OCID:0:50}..."
            echo "   Public IP: $PUBLIC_IP"
            echo "   Keeping instance for debugging..."
            # Don't cleanup - keep for debugging
            KEEP_INSTANCE=true
            exit 1
        fi
        # Show progress every 10 attempts
        if [ $((i % 10)) -eq 0 ]; then
            echo "   ⏳ Still waiting... (${i}/90 attempts, IP: $PUBLIC_IP)"
        fi
        sleep 10
    done
fi

if [ "$SSH_READY" = false ]; then
    echo "❌ SSH never became ready"
    exit 1
fi
echo ""

# Save instance info for potential cleanup
cat > "instances/current-run.env" << EOF
INSTANCE_OCID=$INSTANCE_OCID
REGION=$REGION
PUBLIC_IP=$PUBLIC_IP
PRIVATE_IP=$PRIVATE_IP
INSTANCE_NAME=$INSTANCE_NAME
VERSION=$VERSION
CREATED="$(date)"
EOF

# Instance will be auto-detected on next run (no need to save state)

# Download benchmark suite using Python pipeline
echo "📥 Downloading benchmark suite using Python pipeline..."
BENCHMARK_DIR=$(python3 -c "
import sys
sys.path.append('../benchmark')
from execution.release_manager import KapperReleaseManager
manager = KapperReleaseManager(download_dir='../downloads')
try:
    print(manager.download_version('$VERSION'))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
")

if [ $? -ne 0 ] || [ -z "$BENCHMARK_DIR" ]; then
    echo "❌ Failed to download benchmark suite using Python pipeline"
    if [ "$KEEP_INSTANCE" = false ]; then
        oci compute instance terminate --region "$REGION" --instance-id "$INSTANCE_OCID" --preserve-boot-volume false --force >/dev/null 2>&1 || true
    fi
    exit 1
fi
echo "✅ Benchmark suite ready: $BENCHMARK_DIR"
echo ""

# Deploy benchmarks to instance
echo "🚀 Deploying benchmarks to instance..."

# Clean up any conflicting SSH known_hosts entries (IP reuse can cause conflicts)
echo "   🔧 Clearing SSH known_hosts for IP $PUBLIC_IP..."
ssh-keygen -R "$PUBLIC_IP" >/dev/null 2>&1 || true

# First ensure the home directory exists and has correct permissions
echo "   🔧 Setting up benchmark directory..."

# Fix home directory ownership if needed (cloud-init might have issues)
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "sudo chown -R benchmark:benchmark /home/benchmark && sudo chmod 755 /home/benchmark" 2>/dev/null || true

if ! ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "mkdir -p ~/kapper-benchmarks && chmod 755 ~/kapper-benchmarks"; then
    echo "❌ Failed to create benchmark directory"
    echo "   Debugging: checking home directory permissions..."
    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "ls -la /home/ && ls -la ~/" || true
    if [ "$KEEP_INSTANCE" = false ]; then
        oci compute instance terminate --region "$REGION" --instance-id "$INSTANCE_OCID" --preserve-boot-volume false --force >/dev/null 2>&1 || true
    fi
    exit 1
fi

echo "   📂 Deploying benchmark files..."
if ! rsync -avz -e "ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no" \
    "$BENCHMARK_DIR/" "benchmark@$PUBLIC_IP:~/kapper-benchmarks/"; then
    echo "❌ Failed to deploy benchmarks"
    if [ "$KEEP_INSTANCE" = false ]; then
        oci compute instance terminate --region "$REGION" --instance-id "$INSTANCE_OCID" --preserve-boot-volume false --force >/dev/null 2>&1 || true
    fi
    exit 1
fi
echo "✅ Benchmarks deployed successfully"
echo ""

# Make run scripts executable
echo "🔧 Setting up benchmark scripts..."
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP << 'REMOTE_SETUP'
cd ~/kapper-benchmarks
find . -name "*.sh" -type f -exec chmod +x {} \;
echo "Scripts made executable"
REMOTE_SETUP
echo "✅ Scripts configured"
echo ""

# Run benchmarks
echo "🏃 Running benchmarks..."
if [ "$QUICK_MODE" = true ]; then
    echo "   Mode: Quick (faster, less accurate)"
    BENCHMARK_OPTIONS="-f 1 -i 1"  # 1 fork, 1 iteration for quick testing
else
    echo "   Mode: Full (accurate, slower)"  
    BENCHMARK_OPTIONS=""  # Use default values (3 forks, 5 iterations)
fi

# Check Java installation
echo "🔍 Verifying Java installation..."
if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "java -version" >/dev/null 2>&1; then
    echo "✅ Java is available"
else
    echo "❌ Java not found - installing manually..."
    if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP "sudo apt update && sudo apt install -y openjdk-21-jdk" >/dev/null 2>&1; then
        echo "✅ Java installed successfully"
    else
        echo "❌ Failed to install Java"
        echo "   Instance will be kept for debugging..."
        KEEP_INSTANCE=true
        exit 1
    fi
fi

# Verify environment is ready (cloud-init should have set this up)
echo "🔍 Verifying environment setup..."
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP << 'VERIFY_ENVIRONMENT'
echo "=== Environment Verification ==="

# Check Python
if command -v /usr/local/bin/python3 >/dev/null 2>&1; then
    echo "✅ Python: $(/usr/local/bin/python3 --version)"
    PYTHON_CMD="/usr/local/bin/python3"
elif command -v python3.11 >/dev/null 2>&1; then
    echo "✅ Python: $(python3.11 --version)"
    PYTHON_CMD="python3.11"
elif command -v python3 >/dev/null 2>&1; then
    echo "✅ Python: $(python3 --version)"
    PYTHON_CMD="python3"
else
    echo "❌ No Python found"
    exit 1
fi

# Check container runtime (Podman with Docker compatibility is pre-installed)
if command -v docker >/dev/null 2>&1; then
    echo "✅ Container runtime: $(docker --version 2>&1 | head -1)"
    if docker info >/dev/null 2>&1; then
        echo "✅ Container runtime is working"
        # Set up Docker socket if needed for Testcontainers
        if [ ! -S /var/run/docker.sock ]; then
            echo "Setting up Docker socket for Testcontainers..."
            sudo systemctl enable podman.socket 2>/dev/null || true
            sudo systemctl start podman.socket 2>/dev/null || true
            sudo ln -sf /run/podman/podman.sock /var/run/docker.sock 2>/dev/null || true
        fi
        if [ -S /var/run/docker.sock ]; then
            echo "✅ Docker socket available for Testcontainers"
        fi
    else
        echo "⚠️  Container runtime needs configuration"
    fi
elif command -v podman >/dev/null 2>&1; then
    echo "✅ Container runtime: $(podman --version)"
    echo "✅ Podman is working"
else
    echo "⚠️  No container runtime found, some tests may fail"
fi

# Check Java
if command -v java >/dev/null 2>&1; then
    echo "✅ Java: $(java -version 2>&1 | head -1)"
else
    echo "⚠️  Java not found, will be installed if needed"
fi

echo "=== Environment Ready ==="
VERIFY_ENVIRONMENT

echo "📊 Environment ready for benchmark execution"

# Deploy benchmark package and execute using Python pipeline
echo "🎯 Executing benchmarks using Python pipeline..."
BENCHMARK_SUCCESS=false

# Convert quick mode flag to Python format
PYTHON_QUICK_FLAG=""
if [ "$QUICK_MODE" = true ]; then
    PYTHON_QUICK_FLAG="--quick"
fi

# Deploy benchmark package and requirements to instance
echo "   📦 Deploying benchmark package and requirements..."
if ! rsync -avz -e "ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no" \
    "../benchmark" "../requirements.txt" "benchmark@$PUBLIC_IP:~/"; then
    echo "❌ Failed to deploy benchmark package"
    if [ "$KEEP_INSTANCE" = false ]; then
        oci compute instance terminate --region "$REGION" --instance-id "$INSTANCE_OCID" --preserve-boot-volume false --force >/dev/null 2>&1 || true
    fi
    exit 1
fi
echo "   ✅ Benchmark package and requirements deployed"

# Upload baseline results if specified
if [ -n "$BASELINE_VERSION" ]; then
    echo "   📤 Uploading baseline results for comparison analysis..."
    echo "   Baseline: $BASELINE_VERSION"
    
    # Upload baseline results directory to the instance
    if ! rsync -avz -e "ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no" \
        "../results/$BASELINE_VERSION/" "benchmark@$PUBLIC_IP:~/results/$BASELINE_VERSION/"; then
        echo "❌ Failed to upload baseline results"
        if [ "$KEEP_INSTANCE" = false ]; then
            oci compute instance terminate --region "$REGION" --instance-id "$INSTANCE_OCID" --preserve-boot-volume false --force >/dev/null 2>&1 || true
        fi
        exit 1
    fi
    echo "   ✅ Baseline results uploaded successfully"
    echo ""
fi

# Execute benchmarks using Python pipeline
if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no benchmark@$PUBLIC_IP << REMOTE_BENCH
echo "🚀 Starting Python benchmark pipeline..."

# Determine the best Python to use
if command -v /usr/local/bin/python3 >/dev/null 2>&1; then
    PYTHON_CMD="/usr/local/bin/python3"
    PIP_CMD="/usr/local/bin/pip3"
    echo "Using configured Python 3.11: \$(\$PYTHON_CMD --version)"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
    PIP_CMD="pip3.11"
    echo "Using system Python 3.11: \$(\$PYTHON_CMD --version)"
else
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
    echo "Using system Python: \$(\$PYTHON_CMD --version)"
fi

# Set up PATH to include local bin
export PATH=/usr/local/bin:\$PATH

# Execute everything in tmux session for SSH protection
tmux send-keys -t kapper-benchmark '

# Create and activate virtual environment for benchmark analysis
echo "🔧 Setting up Python virtual environment..."
\$PYTHON_CMD -m venv ~/benchmark-venv
source ~/benchmark-venv/bin/activate

# Install Python dependencies from requirements.txt
echo "📦 Installing Python dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    echo "Using project requirements.txt"
    python -m pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found, using fallback packages"
    python -m pip install requests matplotlib seaborn pandas numpy
fi

# Verify critical dependencies are available
echo "🔍 Verifying Python dependencies..."
python -c "import requests, matplotlib, seaborn, pandas, numpy; print('✅ All dependencies available')" || {
    echo "❌ Python dependencies missing"
    exit 1
}

cd ~/kapper-benchmarks
echo "Working directory: \$(pwd)"

# Set Docker environment for Testcontainers
export DOCKER_HOST=unix:///var/run/docker.sock
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock

# Fix podman socket permissions for Testcontainers (Docker symlinks to podman on Oracle Linux)
echo "🔧 Fixing Docker/Podman socket permissions for Testcontainers..."
# Start podman socket service
sudo systemctl start podman.socket 2>/dev/null || true
sudo systemctl enable podman.socket 2>/dev/null || true

# Fix permissions on the podman directory and socket
sudo chmod 755 /run/podman 2>/dev/null || true
sudo chmod 666 /run/podman/podman.sock 2>/dev/null || true

# Also add user to docker group if it exists (for compatibility)
sudo usermod -aG docker $USER 2>/dev/null || true

# Ensure the docker socket symlink has correct permissions
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true

# Create Testcontainers configuration
mkdir -p ~/.testcontainers
cat > ~/.testcontainers/testcontainers.properties << 'TESTCONTAINERS_CONFIG'
docker.client.strategy=org.testcontainers.dockerclient.UnixSocketClientProviderStrategy
docker.socket=/var/run/docker.sock
testcontainers.reuse.enable=false
TESTCONTAINERS_CONFIG

# Execute benchmark pipeline 
echo "Running: PYTHONPATH=~/:\$PYTHONPATH \$PYTHON_CMD -m benchmark execution $VERSION $PYTHON_QUICK_FLAG --results-dir results"
echo "Docker environment: DOCKER_HOST=\$DOCKER_HOST"
if PYTHONPATH=~/:\$PYTHONPATH \$PYTHON_CMD -m benchmark execution $VERSION $PYTHON_QUICK_FLAG --results-dir results --verbose 2>&1 | tee ~/benchmark_output.log; then
    echo "✅ Python benchmark execution completed successfully"
    echo "\$(date): Benchmark completed successfully" >> ~/benchmark_status.txt
else
    echo "❌ Python benchmark execution failed"
    echo "\$(date): Benchmark failed" >> ~/benchmark_status.txt
fi
' Enter
REMOTE_BENCH
then
    echo "✅ Benchmarks completed successfully"
    BENCHMARK_SUCCESS=true
else
    echo "❌ Benchmark execution failed"
    echo "   Instance will be kept for debugging..."
    KEEP_INSTANCE=true
fi
echo ""

# Download results (only if benchmarks succeeded)
if [ "$BENCHMARK_SUCCESS" = true ]; then
    echo "📥 Downloading ALL benchmark results and artifacts..."
    mkdir -p "$RESULTS_DIR"

    # Download all result files from Python pipeline (JSON, info, reports, etc.)
    echo "   📂 Downloading result files from Python pipeline..."
    if rsync -avz -e "ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no" \
        --include="*.json" \
        --include="*.txt" \
        --include="*.md" \
        --include="*.log" \
        --include="*.csv" \
        --exclude="*" \
        "benchmark@$PUBLIC_IP:~/results/$VERSION/" "$RESULTS_DIR/" 2>/dev/null; then
        echo "   ✅ Result files downloaded from Python pipeline"
    else
        echo "   ⚠️  No result files found from Python pipeline"
        # Fallback: try to download from benchmark directory if Python pipeline failed
        echo "   🔍 Checking for benchmark directory results..."
        rsync -avz -e "ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no" \
            --include="*.json" \
            --include="*.txt" \
            --exclude="*" \
            "benchmark@$PUBLIC_IP:~/kapper-benchmarks/" "$RESULTS_DIR/" 2>/dev/null || true
    fi

    # System info is generated automatically by Python pipeline in info.txt
    echo "   📊 System information captured by Python pipeline"

    # Show comprehensive results summary
    echo ""
    echo "📊 Complete Results Summary:"
    echo "   📁 Results location: $RESULTS_DIR"
    
    # Count different file types
    json_count=$(find "$RESULTS_DIR" -name "*.json" -type f | wc -l)
    txt_count=$(find "$RESULTS_DIR" -name "*.txt" -type f | wc -l)
    md_count=$(find "$RESULTS_DIR" -name "*.md" -type f | wc -l)
    
    echo "   📋 Files downloaded:"
    echo "      JSON files: $json_count"
    echo "      Text files: $txt_count" 
    echo "      Markdown files: $md_count"
    
    # Show JSON file details
    if [ $json_count -gt 0 ]; then
        echo "   📈 Benchmark data files:"
        for result_file in "$RESULTS_DIR"/*.json; do
            if [ -f "$result_file" ]; then
                file_size=$(du -h "$result_file" | cut -f1)
                benchmark_count=$(jq length "$result_file" 2>/dev/null || echo "0")
                echo "      $(basename "$result_file"): ${file_size}, ${benchmark_count} benchmarks"
            fi
        done
    fi
    
    # Show important files
    if [ -f "$RESULTS_DIR/info.txt" ]; then
        echo "   📊 System info: info.txt (generated by Python pipeline)"
    fi
    
else
    echo "⚠️  Skipping result download due to benchmark failure"
fi
echo ""

# Cleanup and reuse management
if [ "$KEEP_INSTANCE" = false ]; then
    echo "🗑️  Cleaning up instance..."
    if oci compute instance terminate \
        --region "$REGION" \
        --instance-id "$INSTANCE_OCID" \
        --preserve-boot-volume false \
        --force >/dev/null 2>&1; then
        echo "✅ Instance terminated"
    else
        echo "⚠️  Failed to terminate instance automatically"
        echo "   Manually terminate: $INSTANCE_OCID"
    fi
    
    rm -f "instances/current-run.env"
else
    echo "💾 Instance preserved for reuse:"
    echo "   Instance ID: ${INSTANCE_OCID:0:50}..."
    echo "   SSH: ssh -i $SSH_KEY_PATH benchmark@$PUBLIC_IP"
    echo "   Terminate when done: ./setup/stop-all-instances.sh"
    echo ""
fi

echo ""
echo "🎉 Benchmark run complete!"
echo "=========================="
echo "   Version: $VERSION"
echo "   Region: $REGION"  
echo "   Results: $RESULTS_DIR"
if [ "$REUSE_INSTANCE" = true ]; then
    echo "   Instance: ${INSTANCE_OCID:0:50}... (reused)"
elif [ "$KEEP_INSTANCE" = true ]; then
    echo "   Instance: ${INSTANCE_OCID:0:50}... (preserved for reuse)"
else
    echo "   Instance: Terminated"
fi
echo ""
if [ "$BENCHMARK_SUCCESS" = true ]; then
    echo "💡 Running complete automated analysis pipeline..."
    
    # Switch to repo root and run complete Python analysis pipeline
    cd ../..
    
    # Set up local Python environment for analysis
    if [ -d "venv" ]; then
        echo "🔧 Activating local virtual environment..."
        source venv/bin/activate
        PYTHON_ANALYSIS_CMD="python"
        echo "✅ Virtual environment activated"
    else
        echo "🔧 Creating local virtual environment for analysis..."
        python3 -m venv venv
        source venv/bin/activate
        echo "📦 Installing analysis dependencies..."
        python -m pip install -r requirements.txt
        PYTHON_ANALYSIS_CMD="python"
        echo "✅ Virtual environment created and configured"
    fi
    
    # Check if we have baseline results for comparison
    if [ -n "$BASELINE_VERSION" ] && [ -d "results/$BASELINE_VERSION" ]; then
        echo "🔍 Running complete analysis pipeline with baseline comparison..."
        echo "   Baseline: $BASELINE_VERSION"
        echo "   Target: $VERSION"
        
        # Run complete analysis pipeline: parsing, comparison, visualization, reports, LLM prompts
        if $PYTHON_ANALYSIS_CMD -m benchmark.reporting.main "$BASELINE_VERSION" "$VERSION" --skip-benchmarks; then
            echo "✅ Complete analysis pipeline finished successfully"
            echo ""
            echo "📊 Generated Analysis Artifacts:"
            echo "   📁 Results directory: results/$VERSION/"
            echo "   📈 Raw benchmark data: results/$VERSION/*.json"
            echo "   📊 System information: results/$VERSION/info.txt"
            echo "   📊 Performance charts: results/$VERSION/graphs/*.png"
            echo "   📋 Analysis report: results/$VERSION/kapper_benchmark_report_*.md"
            echo "   🤖 LLM analysis prompts: results/$VERSION/llm_prompt_*.md"
            echo ""
            echo "💡 Analysis includes:"
            echo "   📈 Version comparison ($BASELINE_VERSION vs $VERSION)"
            echo "   🏆 Library performance comparison (Kapper vs competitors)"
            echo "   📊 Visual charts with performance data"
            echo "   📝 Comprehensive markdown reports"
            echo "   🤖 AI-ready analysis prompts"
        else
            echo "⚠️  Analysis pipeline failed, falling back to basic parsing..."
            # Fallback to just parsing using benchmark analysis module
            if $PYTHON_ANALYSIS_CMD -m benchmark.analysis.main parse "results/$VERSION" "$VERSION"; then
                echo "✅ Basic result parsing completed"
            else
                echo "⚠️  Result parsing also failed, but raw results are available"
            fi
        fi
    else
        if [ -n "$BASELINE_VERSION" ]; then
            echo "🔍 Running analysis for single version (baseline upload may have failed)..."
            echo "   Note: Baseline was specified ($BASELINE_VERSION) but not found in results directory"
        else
            echo "🔍 Running analysis for single version (no baseline specified)..."
        fi
        
        # Run analysis for single version only using benchmark reporting module
        if $PYTHON_ANALYSIS_CMD -m benchmark.reporting.main "$VERSION" --skip-benchmarks; then
            echo "✅ Result parsing completed"
            echo ""
            echo "📊 Generated Analysis Artifacts:"
            echo "   📁 Results directory: results/$VERSION/"
            echo "   📈 Raw benchmark data: results/$VERSION/*.json"
            echo "   📊 System information: results/$VERSION/info.txt"
            echo ""
            if [ -n "$BASELINE_VERSION" ]; then
                echo "💡 To generate complete analysis with comparison:"
                echo "   📋 Ensure baseline exists: results/$BASELINE_VERSION/"
                echo "   📈 Then run: python -m benchmark.reporting.main $BASELINE_VERSION $VERSION --skip-benchmarks"
            else
                echo "💡 To generate complete analysis with comparison:"
                echo "   📋 Run with baseline: $0 $VERSION --baseline <baseline_version>"
                echo "   📈 Or run analysis later: python -m benchmark.reporting.main <baseline> $VERSION --skip-benchmarks"
            fi
        else
            echo "⚠️  Result parsing failed, but raw results are available"
        fi
    fi
    
    # Stay in project root directory
fi

echo "   List instances: ./setup/list-all-instances.sh"