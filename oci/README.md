# OCI Cloud Deployment for Kapper Benchmarks

**Automated Oracle Cloud Infrastructure deployment** with **SSH disconnection protection** for running Kapper benchmarks on free-tier ARM compute instances with:

- **🔐 SSH disconnection protection** (tmux session persistence)
- **🌐 Multi-region capacity detection** (us-phoenix-1, ca-toronto-1, uk-london-1)
- **🔄 Intelligent instance reuse** (5-8 minute savings per run)  
- **🐳 Full database testing** (PostgreSQL via Testcontainers + SQLite)
- **🛡️ Dynamic security** (IP-restricted SSH access)
- **💰 Cost protection** (Always Free ARM instances with auto-cleanup)

## 🚀 Quick Start

```bash
# 1. One-time infrastructure setup across regions
./setup/setup-prerequisites.sh

# 2. Run complete benchmark pipeline with SSH protection
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0

# 3. Monitor progress (reconnect safely after disconnection)
./monitor-benchmark.sh --reconnect

# 4. Quick testing with instance reuse (faster, for development)
./setup/run-benchmarks.sh 1.6.1 --quick

# 5. Monitor instances across all regions
./setup/list-all-instances.sh

# 6. Emergency cleanup - terminate all instances
./setup/stop-all-instances.sh
```

## 📋 Prerequisites

### 1. OCI Account Setup

- Create free Oracle Cloud account
- Note your tenancy OCID and region
- Create API key pair for CLI access

### 2. Install OCI CLI

```bash
# macOS
brew install oci-cli

# Linux
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
```

### 3. Configure OCI CLI

```bash
oci setup config
```

You'll need:
- User OCID
- Tenancy OCID  
- Region (e.g., uk-london-1)
- API Key (will generate if needed)

## 🏗️ Architecture

### Multi-Region Support
- **us-phoenix-1**: US West (Phoenix) - Primary ARM capacity
- **ca-toronto-1**: Canada (Toronto) - Secondary capacity
- **uk-london-1**: UK (London) - Home region

### Instance Specifications
- **Shape**: VM.Standard.A1.Flex (ARM-based)
- **OCPUs**: 4 (free tier maximum)
- **Memory**: 24GB (free tier maximum)
- **OS**: Oracle Linux Cloud Developer 8.9 ARM64 (pre-installed JDK)
- **Storage**: Boot volume with auto-delete

### Software Stack
- **Java**: GraalVM JDK 21 LTS (pre-installed in Oracle Linux Cloud Developer)
- **Benchmarks**: JMH (Java Microbenchmark Harness) via Python pipeline
- **Python**: Used for benchmark execution pipeline integration
- **SSH Protection**: Tmux session persistence for disconnection protection
- **Deployment**: rsync for efficient file transfer
- **Cloud-Init**: Automated instance configuration

### Network Architecture (Per Region)
- **VCN**: Virtual Cloud Network (10.0.0.0/16)
- **Internet Gateway**: Public internet access
- **Route Table**: Routes traffic to internet gateway
- **Security List**: SSH access restricted to your public IP
- **Public Subnet**: Instance deployment subnet

## 📚 Script Overview

### Core Scripts (5-Script Architecture)

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup-prerequisites.sh` | One-time infrastructure setup | `./setup/setup-prerequisites.sh` |
| `run-benchmarks.sh` | Complete benchmark execution with tmux protection | `./setup/run-benchmarks.sh <version> [options]` |
| `monitor-benchmark.sh` | Enhanced monitoring with reconnection | `./monitor-benchmark.sh [--reconnect\|--once]` |
| `list-all-instances.sh` | Multi-region instance monitoring | `./setup/list-all-instances.sh` |
| `stop-all-instances.sh` | Emergency cleanup across regions | `./setup/stop-all-instances.sh [--remove-terminated]` |

### Benchmark Options

```bash
# Standard benchmark run (auto-reuses instances)
./setup/run-benchmarks.sh 1.6.1

# Quick mode (faster, less accurate, auto-reuses instances)
./setup/run-benchmarks.sh 1.6.1 --quick

# Run with baseline comparison (uploads local baseline results)
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0

# Combined: quick testing with baseline comparison
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0 --quick

# Keep instance running for debugging and future reuse
./setup/run-benchmarks.sh 1.6.1 --keep-instance

# Force new instance (terminates existing instances for clean testing)
./setup/run-benchmarks.sh 1.6.1 --force-new-instance
```

### Monitoring Options

```bash
# Enhanced monitoring with tmux session management
./monitor-benchmark.sh                    # Continuous monitoring
./monitor-benchmark.sh --reconnect        # Reconnect to existing sessions
./monitor-benchmark.sh --once             # Single status check

# Show all instances with state details
./setup/list-all-instances.sh

# Stop all running instances
./setup/stop-all-instances.sh

# Force cleanup of terminated instances (optional)
./setup/stop-all-instances.sh --remove-terminated
```

## 🎯 Usage Workflows

### First-Time Setup

```bash
# 1. Configure OCI CLI
oci setup config

# 2. Setup infrastructure (creates VCNs, subnets, security groups)
cd oci/
./setup/setup-prerequisites.sh

# 3. Run your first benchmark
./setup/run-benchmarks.sh 1.6.1
```

### Regular Benchmark Execution

```bash
# Standard full benchmarks (auto-reuses instances, SSH protected)
./setup/run-benchmarks.sh 1.6.1

# Monitor progress (reconnect if disconnected)
./monitor-benchmark.sh --reconnect

# Quick testing mode (auto-reuses instances for fast iterations)
./setup/run-benchmarks.sh 1.6.1 --quick

# Force clean testing environment
./setup/run-benchmarks.sh 1.6.1 --force-new-instance

# Monitor running instances
./setup/list-all-instances.sh
```

### SSH Disconnection Protection

```bash
# Benchmarks run in tmux sessions automatically
./setup/run-benchmarks.sh 1.6.1

# If you get disconnected, reconnect with:
./monitor-benchmark.sh --reconnect

# Or manually connect to tmux session:
ssh -i ~/.ssh/kapper-benchmark benchmark@<ip> 'tmux attach -t kapper-benchmark'

# Monitor without connecting (continuous)
./monitor-benchmark.sh

# Single status check
./monitor-benchmark.sh --once
```

### Debugging and Development

```bash
# Keep instance for debugging
./setup/run-benchmarks.sh 1.6.1 --keep-instance

# SSH to preserved instance (shown in output)
ssh -i ~/.ssh/kapper-benchmark benchmark@<public-ip>

# Access benchmark logs
ssh -i ~/.ssh/kapper-benchmark benchmark@<ip> 'tail -f ~/benchmark_output.log'

# Stop all instances when done
./setup/stop-all-instances.sh
```

## 🔧 Configuration Files

The setup creates environment files for persistence:

```
oci/instances/
├── prerequisites.env              # Global configuration
│   ├── ACCESSIBLE_REGIONS         # Regions with permissions
│   ├── SSH_KEY_PATH               # SSH key location
│   ├── SSH_SOURCE                 # Your public IP for security
│   └── COMPARTMENT_ID             # OCI compartment
├── network-us-phoenix-1.env       # Network config per region
├── network-ca-toronto-1.env       
├── network-uk-london-1.env        
└── current-run.env                # Active instance details (temporary)
```

## 📊 Output Structure

Results are organized in the main results directory:

```
../results/
└── <version>/                     # Version-specific results
    ├── *.json                     # JMH benchmark results
    ├── info.txt                   # System information
    ├── graphs/                    # Performance charts (if generated)
    │   └── *.png
    ├── *.md                       # Analysis reports (if generated)
    └── llm_prompt_*.md           # AI analysis prompts (if generated)
```

## 💰 Cost Management

### Free Tier Benefits
- **Compute**: VM.Standard.A1.Flex up to 4 OCPUs (Always Free)
- **Memory**: Up to 24GB RAM (Always Free)
- **Storage**: Boot volumes (included in free tier)
- **Network**: Egress included in free tier

### Cost Protection Features
- **Automatic termination**: Instances terminate after benchmark completion
- **IP-restricted access**: Security groups prevent unauthorized usage
- **Multi-region capacity**: Finds free capacity automatically
- **Emergency cleanup**: `stop-all-instances.sh` terminates everything immediately

### Monitoring Costs
```bash
# Check current instances
./setup/list-all-instances.sh

# Emergency stop all instances
./setup/stop-all-instances.sh

# OCI Console monitoring
# Navigate to: Billing & Cost Management → Cost Analysis
```

## 🔍 Monitoring & Troubleshooting

### Capacity Detection
The system automatically finds ARM capacity across regions:
1. Tests us-phoenix-1 (best availability)
2. Falls back to ca-toronto-1
3. Falls back to uk-london-1
4. Reports if no capacity available

### Instance States
- **🟢 RUNNING**: Active and incurring charges (if not free tier)
- **🔴 STOPPED**: Stopped, no compute charges
- **⚫ TERMINATED**: Terminated, will auto-cleanup in 24-48 hours
- **🟡 STARTING/STOPPING/TERMINATING**: Transitional states

### Common Issues

| Issue | Cause | Solution |
|-------|-------|---------|
| No ARM capacity | Free tier exhausted | Try different regions or wait |
| SSH connection fails | Instance still starting | Wait 2-3 minutes for cloud-init |
| Prerequisites fail | No OCI permissions | Check compartment permissions |
| Network setup fails | Existing resources | Delete existing VCNs or use different names |

### Debug Commands

```bash
# Check instance details
./setup/list-all-instances.sh

# View cloud-init logs (SSH to instance)
ssh -i ~/.ssh/kapper-benchmark benchmark@<ip> 'sudo tail -f /var/log/cloud-init-output.log'

# Monitor benchmark execution
ssh -i ~/.ssh/kapper-benchmark benchmark@<ip> 'cd ~/kapper-benchmarks && tail -f *.log'
```

## 🛡️ Security Features

- **Dynamic IP restriction**: SSH access limited to your current public IP
- **Key-based authentication**: SSH keys auto-generated and managed
- **Isolated networking**: Each region has separate VCN
- **Automatic cleanup**: Instances terminate after use
- **No persistent storage**: No data retention risks

## 🚀 Advanced Features

### Automated Capacity Detection
- Tests multiple regions for ARM availability
- Selects first region with capacity
- Handles OCI capacity limitations gracefully

### Smart Instance Management
- **Dynamic Instance Detection**: Real-time scanning for running instances (no stale config files)
- **Intelligent Reuse**: Tests SSH connectivity before reusing instances, terminates broken ones
- **Multi-Instance Cleanup**: Automatically terminates multiple instances to prevent resource waste
- **Robust SSH Testing**: Multiple retry attempts with fallback strategies for reliable connections
- **Force New Instance**: `--force-new-instance` terminates existing instances and creates fresh one for clean testing
- **Cost Control**: Ensures only one instance runs at a time across all regions

### Performance Optimization
- **Fast Testing Cycles**: Reuse existing instances instead of 5-8 minute setup
- **Intelligent Fallback**: Creates new instances when reusable ones aren't available
- **Stateless Design**: No config file management - instances detected dynamically

### Docker and Testcontainers Support
- **Automatic Docker Installation**: Instances automatically install Docker CE from official repository
- **Podman Conflict Resolution**: Automatically removes conflicting Podman installation that comes with Oracle Linux
- **Testcontainers Compatibility**: Full support for Kapper benchmarks that use Testcontainers for database testing
- **Rootless Docker Access**: Benchmark user automatically added to docker group for seamless access
- **Docker Verification**: Pre-benchmark Docker health checks ensure container functionality
- **Socket Management**: Ensures proper Docker socket permissions and removes Podman symlinks

### Baseline Comparison Support
- **Local Baseline Upload**: Automatically uploads local baseline results to cloud instances
- **Version Comparison**: Compare any version against a locally available baseline
- **Validation**: Validates baseline completeness before upload (info.txt, benchmark JSONs)
- **Complete Analysis**: Generates charts, reports, and LLM prompts with version comparison
- **Fallback Handling**: Graceful degradation if baseline upload fails

### Integration with Analysis Pipeline
```bash
# Run benchmarks on OCI
./setup/run-benchmarks.sh 1.6.1

# Analyze results locally (same as local benchmarks)
cd ..
python reporting/main.py 1.5.0 1.6.1 --skip-benchmarks
```

## 📖 Additional Resources

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [OCI CLI Documentation](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/)
- [ARM Instance Documentation](https://docs.oracle.com/en-us/iaas/Content/Compute/References/arm-based-instances.htm)
- [Eclipse Temurin JDK](https://adoptium.net/temurin/releases/) (Free License)

## 🔄 Migration from Legacy Scripts

If you have old OCI scripts (9-script architecture), this new system replaces:
- ❌ `find-free-tier-capacity.sh` → ✅ Built into `run-benchmarks.sh`
- ❌ `setup-network-region.sh` → ✅ `setup-prerequisites.sh`
- ❌ `create-instance-region.sh` → ✅ Built into `run-benchmarks.sh`
- ❌ `deploy-benchmarks.sh` → ✅ Built into `run-benchmarks.sh`
- ❌ `run-remote-benchmarks.sh` → ✅ Built into `run-benchmarks.sh`
- ❌ `retrieve-results.sh` → ✅ Built into `run-benchmarks.sh`
- ❌ Multiple instance management scripts → ✅ `list-all-instances.sh` + `stop-all-instances.sh`

The new system provides the same functionality with better reliability, security, and ease of use.