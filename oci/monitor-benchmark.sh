#!/bin/bash

# Monitor benchmark progress on OCI instances with reconnection capability
# Usage: ./monitor-benchmark.sh [--once|--reconnect]

set -euo pipefail

# Configuration
SSH_KEY_PATH="$HOME/.ssh/kapper-benchmark"
CONTINUOUS_MODE=true
RECONNECT_MODE=false
REFRESH_INTERVAL=30  # seconds

# Parse arguments
if [[ "${1:-}" == "--once" ]]; then
    CONTINUOUS_MODE=false
    echo "📋 Single check mode"
    echo ""
elif [[ "${1:-}" == "--reconnect" ]]; then
    RECONNECT_MODE=true
    echo "🔗 Reconnection mode - will connect to existing tmux session if found"
    echo ""
else
    echo "🔄 Continuous monitoring mode (refresh every ${REFRESH_INTERVAL}s, Ctrl+C to exit)"
    echo "💡 Use --once for a single check or --reconnect to connect to existing session"
    echo ""
fi


# Auto-reconnect if we find a running session
auto_reconnect_if_needed() {
    local ip="$1"
    local instance_name="$2"
    
    # Check if there's a tmux session running
    local tmux_session=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "tmux list-sessions 2>/dev/null | grep 'kapper-benchmark'" 2>/dev/null || echo "")
    
    if [ -n "$tmux_session" ]; then
        echo "🔗 Found active tmux session on $instance_name!"
        echo "   Session: $tmux_session"
        echo ""
        echo "💬 Would you like to reconnect to the running benchmark?"
        echo "   1) Yes - connect to tmux session"
        echo "   2) No - just monitor from outside"
        echo "   3) Exit"
        
        read -p "Choose (1-3) [default: 1]: " -t 10 CHOICE || CHOICE="1"
        echo ""
        
        case "${CHOICE:-1}" in
            1)
                echo "🔗 Connecting to tmux session..."
                echo "💡 Press Ctrl+B then D to detach and return to monitoring"
                echo "💡 Press Ctrl+C to interrupt current command"
                echo ""
                
                # Connect to the tmux session (check if interactive)
                if [ -t 0 ]; then
                    # Interactive terminal
                    if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -t \
                       benchmark@"$ip" \
                       "tmux attach-session -t kapper-benchmark"; then
                        echo "🔄 Disconnected from session"
                    else
                        echo "❌ Failed to connect to session"
                    fi
                else
                    # Non-interactive - show recent output
                    echo "🔍 Non-interactive terminal - showing recent output:"
                    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
                        benchmark@"$ip" \
                        "tmux capture-pane -t kapper-benchmark -p | tail -15" 2>/dev/null || echo "Could not capture session"
                fi
                echo ""
                return 0
                ;;
            2)
                echo "🔍 Continuing with external monitoring..."
                return 0
                ;;
            3)
                echo "👋 Goodbye!"
                exit 0
                ;;
            *)
                echo "🔍 Invalid choice, continuing with monitoring..."
                return 0
                ;;
        esac
    fi
    
    return 1  # No session found
}

# Check status of a specific instance
check_instance_status() {
    local ip="$1"
    local instance_name="$2"
    
    echo ""
    echo "🚀 Checking benchmark status on $instance_name ($ip)..."
    
    # Test SSH connectivity
    if ! ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
         benchmark@"$ip" "echo 'Connected'" >/dev/null 2>&1; then
        echo "   ❌ SSH connection failed"
        return 2
    fi
    
    # Check tmux session first
    local tmux_session=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "tmux list-sessions 2>/dev/null | grep 'kapper-benchmark'" 2>/dev/null || echo "")
    
    if [ -n "$tmux_session" ]; then
        echo "   📱 Tmux session active: $tmux_session"
        
        # Get last few lines from benchmark output log
        local tmux_output=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
            benchmark@"$ip" \
            "tail -3 ~/benchmark_output.log 2>/dev/null" || echo "")
        
        if [ -n "$tmux_output" ]; then
            echo "   📝 Recent benchmark output:"
            echo "$tmux_output" | sed 's/^/     🔸 /'
        fi
        
        # Return 0 = still running
        return 0
    fi
    
    # Check regular processes if no tmux session
    local processes=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "ps aux | grep -E '(java.*benchmark|python.*benchmark)' | grep -v grep" 2>/dev/null || echo "")
    
    if [ -n "$processes" ]; then
        echo "   ✅ Benchmark processes running:"
        echo "$processes" | while read -r process; do
            echo "     🔸 $(echo "$process" | awk '{print $11, $12, $13, $14, $15}' | cut -c1-80)"
        done
        
    else
        echo "   ❌ No benchmark processes running"
        
        # Check if there are completed results
        echo "   🔍 Checking for completed results..."
        local completed_results=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
            benchmark@"$ip" \
            "cd ~/kapper-benchmarks 2>/dev/null && find . -name '*.json' -type f -size +0 2>/dev/null | wc -l" || echo "0")
        
        if [ "$completed_results" -gt 0 ]; then
            echo "   ✅ Found $completed_results completed result file(s)"
            ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
                benchmark@"$ip" \
                "cd ~/kapper-benchmarks 2>/dev/null && find . -name '*.json' -type f -size +0 -exec ls -lh {} \;" | \
            while read -r line; do
                local size=$(echo "$line" | awk '{print $5}')
                local file=$(echo "$line" | awk '{print $9}')
                echo "     ✅ $file ($size)"
            done
            
            # Return status: 1 = completed
            return 1
        else
            echo "   ❌ No completed results found"
            # Return status: 1 = completed (but no results - likely failed)
            return 1
        fi
    fi
    
    # Check result files (for running processes)
    echo ""
    echo "   📁 Checking result files..."
    local result_files=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "cd ~/kapper-benchmarks 2>/dev/null && find . -name '*.json' -type f -exec ls -lh {} \; 2>/dev/null | grep -v '^total'" || echo "")
    
    if [ -n "$result_files" ]; then
        echo "   📄 Result files found:"
        echo "$result_files" | while read -r line; do
            local size=$(echo "$line" | awk '{print $5}')
            local file=$(echo "$line" | awk '{print $9}')
            local modified=$(echo "$line" | awk '{print $6, $7, $8}')
            
            if [ "$size" = "0" ]; then
                echo "     ⏳ $file (empty - in progress) [$modified]"
            else
                echo "     ✅ $file ($size) [$modified]"
            fi
        done
    else
        echo "   📄 No result files found yet"
    fi
    
    # Check log output (last few lines from benchmark_output.log)
    echo ""
    echo "   📋 Recent activity:"
    local benchmark_log=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "tail -5 ~/benchmark_output.log 2>/dev/null" || echo "")
    
    if [ -n "$benchmark_log" ]; then
        echo "$benchmark_log" | sed 's/^/     📝 /'
    else
        # Fallback to other logs
        local recent_logs=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
            benchmark@"$ip" \
            "cd ~/kapper-benchmarks 2>/dev/null && find . -name '*.log' -o -name 'nohup.out' 2>/dev/null | head -1 | xargs tail -5 2>/dev/null" || echo "")
        
        if [ -n "$recent_logs" ]; then
            echo "$recent_logs" | sed 's/^/     📝 /'
        else
            echo "     📝 No recent log output found"
        fi
    fi
    
    # Check benchmark status
    local benchmark_status=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
        benchmark@"$ip" \
        "cat ~/benchmark_status.txt 2>/dev/null | tail -1" || echo "")
    
    if [ -n "$benchmark_status" ]; then
        echo "   📊 Benchmark status: $benchmark_status"
    fi
    
    # Return status: 0 = still running
    return 0
}

# Main monitoring loop
monitor_loop() {
    local any_running=true
    
    while true; do
        clear
        echo "🎯 Kapper Benchmark Progress Monitor"
        echo "===================================="
        echo "$(date '+%Y-%m-%d %H:%M:%S')"
        if [ "$RECONNECT_MODE" = true ]; then
            echo "🔗 Reconnection mode: Will connect to active sessions"
        fi
        echo ""
        
        any_running=false
        
        # Check instances and track if any are still running
        if [ -f "instances/network-us-phoenix-1.env" ]; then
            source instances/network-us-phoenix-1.env
            
            # Get running benchmark instances
            local benchmark_instances=$(oci compute instance list \
                --region us-phoenix-1 \
                --compartment-id "$COMPARTMENT_ID" \
                --lifecycle-state RUNNING \
                --query 'data[].[id,"display-name"]' \
                --output json 2>/dev/null | \
            jq -r '.[] | select(.[1] | contains("kapper-benchmark")) | @tsv' || echo "")
            
            if [ -n "$benchmark_instances" ]; then
                echo "📋 Scanning for running benchmark instances..."
                echo ""
                
                # On first run, check if we should auto-reconnect
                local first_instance=true
                
                while IFS=$'\t' read -r instance_id display_name; do
                    # Get public IP
                    local vnic_id=$(oci compute vnic-attachment list \
                        --region us-phoenix-1 \
                        --compartment-id "$COMPARTMENT_ID" \
                        --instance-id "$instance_id" \
                        --query 'data[0]."vnic-id"' \
                        --raw-output 2>/dev/null || echo "")
                    
                    if [ -n "$vnic_id" ] && [ "$vnic_id" != "null" ]; then
                        local public_ip=$(oci network vnic get \
                            --region us-phoenix-1 \
                            --vnic-id "$vnic_id" \
                            --query 'data."public-ip"' \
                            --raw-output 2>/dev/null || echo "")
                        
                        if [ -n "$public_ip" ] && [ "$public_ip" != "null" ]; then
                            echo "🔍 Instance: $display_name ($public_ip)"
                            
                            # On first instance, try auto-reconnect
                            if [ "$first_instance" = true ] && [ "$RECONNECT_MODE" = true ]; then
                                first_instance=false
                                if auto_reconnect_if_needed "$public_ip" "$display_name"; then
                                    # User chose to reconnect or continue monitoring
                                    true
                                fi
                            fi
                            
                            # Check this instance status
                            check_instance_status "$public_ip" "$display_name"
                            local status=$?
                            
                            if [ $status -eq 0 ]; then
                                any_running=true
                                
                                # If in reconnect mode and we found an active tmux session, connect to it
                                if [ "$RECONNECT_MODE" = true ]; then
                                    echo ""
                                    echo "🔗 Reconnecting to tmux session on $display_name..."
                                    echo "💡 Press Ctrl+B then D to detach (leave running)"
                                    echo "💡 Press Ctrl+C to interrupt current command"
                                    read -p "Press Enter to connect..." -t 5 || echo ""
                                    
                                    # Connect to the tmux session (check if interactive)
                                    if [ -t 0 ]; then
                                        # Interactive terminal
                                        ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -t \
                                            benchmark@"$public_ip" \
                                            "tmux attach-session -t kapper-benchmark 2>/dev/null || echo 'Session not found, opening regular SSH'; bash"
                                        echo "🔄 Disconnected from session. Continuing monitoring..."
                                    else
                                        # Non-interactive - show detailed output
                                        echo "🔍 Non-interactive terminal - showing detailed session output:"
                                        ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no \
                                            benchmark@"$public_ip" \
                                            "echo '=== Recent benchmark output (last 20 lines) ==='; tmux capture-pane -t kapper-benchmark -p | tail -20; echo ''; echo '=== Benchmark log ==='; tail -10 ~/benchmark_output.log 2>/dev/null || echo 'No log yet'"
                                        echo "📊 Detailed output shown. Continuing monitoring..."
                                    fi
                                    echo ""
                                fi
                            elif [ $status -eq 1 ]; then
                                echo "   🎉 Benchmarks completed on this instance!"
                                
                                if [ "$RECONNECT_MODE" = true ]; then
                                    echo "🔗 Connecting to completed instance for result inspection..."
                                    read -p "Press Enter to connect..." -t 3 || echo ""
                                    
                                    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -t \
                                        benchmark@"$public_ip" \
                                        "echo 'Benchmark completed. Results:'; find . -name '*.json' -exec ls -lh {} \;; bash"
                                fi
                            fi
                        fi
                    fi
                done <<< "$benchmark_instances"
            else
                echo "❌ No running benchmark instances found"
            fi
        else
            echo "❌ Network configuration not found for us-phoenix-1"
        fi
        
        # Exit conditions
        if [ "$CONTINUOUS_MODE" = false ]; then
            break
        fi
        
        if [ "$any_running" = false ]; then
            echo ""
            echo "🎉 All benchmarks completed! Monitoring stopped."
            break
        fi
        
        echo ""
        echo "🔄 Refreshing in ${REFRESH_INTERVAL} seconds... (Ctrl+C to exit)"
        sleep "$REFRESH_INTERVAL"
    done
}

# Check if we're in the correct directory
if [ ! -f "setup/run-benchmarks.sh" ]; then
    echo "❌ Please run this script from the oci directory (where setup/run-benchmarks.sh exists)"
    exit 1
fi

# Check if required tools are available
command -v oci >/dev/null 2>&1 || { echo "❌ OCI CLI not found. Please install it first."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "❌ jq not found. Please install it first."; exit 1; }

# Check if SSH key exists
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "❌ SSH key not found at $SSH_KEY_PATH"
    exit 1
fi

# Run monitoring
monitor_loop

echo ""
echo "✅ Monitoring complete"