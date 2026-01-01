#!/usr/bin/env python3
"""
Kapper Benchmark Executor

Executes JMH benchmarks using the run.sh script from downloaded benchmark suites.
"""

import os
import subprocess
import shutil
from pathlib import Path


class BenchmarkExecutor:
    """Executes Kapper benchmarks."""
    
    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
    
    def _run_single_benchmark(self, script_name: str, benchmark_dir: Path, version_results_dir: Path, 
                              result_prefix: str, quick: bool = False, original_cwd: Path = None):
        """Run a single benchmark script and collect its results.
        
        Args:
            script_name: Name of script to run (e.g., "run.sh", "run-mapper.sh")
            benchmark_dir: Path to benchmark directory
            version_results_dir: Path to store results
            result_prefix: Prefix for result files (e.g., "main", "mapper")
            quick: Whether to use quick mode parameters
        """
        script_path = benchmark_dir / script_name
        if not script_path.exists():
            print(f"Warning: {script_name} not found, skipping")
            return
        
        # Make script executable if needed
        current_permissions = script_path.stat().st_mode
        if not (current_permissions & 0o100):
            script_path.chmod(0o755)
            print(f"Made {script_name} executable")
        
        print(f"Running {script_name}...")
        
        # Build command with quick mode parameters if needed
        if quick:
            # For quick mode, call JMH directly to have full control over parameters
            jar_file = None
            for jar in Path(".").glob("*.jar"):
                if "jmh" in jar.name:
                    jar_file = jar
                    break
            
            if not jar_file:
                print(f"Warning: No JMH jar found for quick mode, falling back to script")
                cmd = [f"./{script_name}"]
            else:
                print(f"Quick mode: Running JMH directly with minimal parameters")
                if script_name == "run-mapper.sh":
                    # Mapper benchmark - minimal scenarios
                    cmd = ["java", "-jar", str(jar_file), 
                          "-bm", "avgt", "-f", "1", "-i", "1", "-r", "1s", "-wi", "0",
                          "-p", "scenario=SIMPLE-NOREFLECTION,SIMPLE-DATACLASS", 
                          "-p", "numberOfResults=10",
                          "-rf", "json", "-rff", "mapper-results-avgt.json"]
                    print("Quick mapper mode: 1 fork, 1 iteration, 1s runtime, 0 warmup iterations, 2 scenarios, 10 results")
                else:  # run.sh
                    # Main benchmark - minimal libraries and databases
                    cmd = ["java", "-jar", str(jar_file),
                          "-bm", "avgt", "-f", "1", "-i", "1", "-r", "1s", "-wi", "0", 
                          "-p", "databaseType=SQLITE", 
                          "-p", "library=JDBC,KAPPER", 
                          "-p", "rows=10",
                          "-rf", "json", "-rff", "main-results-avgt.json"]
                    print("Quick main mode: 1 fork, 1 iteration, 1s runtime, 0 warmup iterations, SQLITE only, 2 libraries, 10 rows")
        else:
            # Normal mode - use the scripts
            cmd = [f"./{script_name}"]
        
        # Run the benchmark
        result = subprocess.run(cmd, universal_newlines=True, check=False)
        
        if result.returncode != 0:
            print(f"Warning: {script_name} execution failed with return code {result.returncode}")
            return
        
        # Copy results immediately with proper naming
        # Use absolute paths to avoid issues with working directory changes
        benchmark_dir_abs = benchmark_dir.resolve()
        # Use the passed original_cwd to resolve the correct results directory
        if original_cwd:
            version_results_dir_abs = (original_cwd / self.results_dir / version_results_dir.name).resolve()
        else:
            version_results_dir_abs = version_results_dir.resolve()
        
        for result_file in ["results-avgt.json", "results-ss.json"]:
            source_file = benchmark_dir_abs / result_file
            if source_file.exists():
                target_file = version_results_dir_abs / f"{result_prefix}-{result_file}"
                print(f"Attempting to copy {source_file} to {target_file}")
                try:
                    # Ensure target directory exists
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target_file)
                    print(f"Successfully copied {result_file} to {target_file}")
                    source_file.unlink()
                except Exception as e:
                    print(f"Error copying {source_file} to {target_file}: {e}")
            else:
                print(f"Source file {source_file} does not exist")
    
    def run_benchmark(self, benchmark_dir: Path, version: str, quick: bool = False) -> Path:
        """Run benchmark suite and collect results.
        
        Args:
            benchmark_dir: Path to extracted benchmark suite
            version: Kapper version being tested
            quick: If True, run minimal benchmarks for fast testing
            
        Returns:
            Path to results directory for this version
        """
        
        if not benchmark_dir.exists():
            raise RuntimeError(f"Benchmark directory does not exist: {benchmark_dir}")
        
        run_script = benchmark_dir / "run.sh"
        if not run_script.exists():
            raise RuntimeError(f"Run script not found: {run_script}")
        
        # Create version-specific results directory
        version_results_dir = self.results_dir / version
        version_results_dir.mkdir(exist_ok=True)
        
        print(f"Running benchmark for Kapper {version}...")
        print(f"Results will be saved to: {version_results_dir}")
        
        # Change to benchmark directory and run benchmarks
        original_cwd = Path.cwd()
        try:
            os.chdir(benchmark_dir)
            
            # Run main benchmark suite first (core benchmarks)
            self._run_single_benchmark("run.sh", Path("."), version_results_dir, "main", quick, original_cwd)
            
            # Run mapper benchmark suite (supplementary benchmarks)
            self._run_single_benchmark("run-mapper.sh", Path("."), version_results_dir, "mapper", quick, original_cwd)
            
            print("All benchmarks completed successfully!")
            
            # Create info file
            self._create_info_file(version_results_dir, version, benchmark_dir, original_cwd)
            
        finally:
            os.chdir(original_cwd)
        
        return version_results_dir
    
    def _create_info_file(self, results_dir: Path, version: str, benchmark_dir: Path, original_cwd: Path):
        """Create info file with benchmark details."""
        
        # Use absolute path to ensure info.txt goes to correct location
        if original_cwd:
            info_file = (original_cwd / self.results_dir / results_dir.name / "info.txt").resolve()
        else:
            info_file = results_dir / "info.txt"
        with open(info_file, 'w') as f:
            f.write(f"Kapper {version} Benchmark Results\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated automatically by benchmark pipeline\n\n")
            
            # Copy system info if available from stdout
            jar_file = next(benchmark_dir.glob("kapper-benchmark-*-jmh.jar"), None)
            if jar_file:
                # Get SHA-256 of JAR file
                sha_result = subprocess.run(
                    ["shasum", "-a", "256", str(jar_file)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                if sha_result.returncode == 0:
                    sha = sha_result.stdout.split()[0]
                    f.write(f"JMH benchmark JAR: {jar_file.name} (SHA-256: {sha})\n")
            
            f.write(f"Kapper version: {version}\n")
            
            # Add Java version info
            java_result = subprocess.run(
                ["java", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            if java_result.returncode == 0:
                f.write("\nJava version:\n")
                f.write(java_result.stderr)  # Java version goes to stderr
            
            # Add system info
            f.write("\nSystem info:\n")
            
            # Get current date and hostname
            import datetime
            import socket
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Hostname: {socket.gethostname()}\n")
            
            # OS information
            if Path("/etc/os-release").exists():
                try:
                    os_info = subprocess.run(
                        ["grep", "PRETTY_NAME", "/etc/os-release"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    if os_info.returncode == 0:
                        os_name = os_info.stdout.split("=")[1].strip().strip('"')
                        f.write(f"OS: {os_name}\n")
                except Exception:
                    pass
            
            # Kernel version
            try:
                kernel_result = subprocess.run(
                    ["uname", "-r"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                if kernel_result.returncode == 0:
                    f.write(f"Kernel: {kernel_result.stdout.strip()}\n")
            except Exception:
                pass
            
            # Architecture
            try:
                arch_result = subprocess.run(
                    ["uname", "-m"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                if arch_result.returncode == 0:
                    f.write(f"Architecture: {arch_result.stdout.strip()}\n")
            except Exception:
                pass
            
            # CPU information
            if shutil.which("lscpu"):  # Linux
                try:
                    cpu_result = subprocess.run(
                        ["lscpu"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    if cpu_result.returncode == 0:
                        for line in cpu_result.stdout.split('\n'):
                            if 'Model name:' in line:
                                cpu_name = line.split(':', 1)[1].strip()
                                f.write(f"CPU: {cpu_name}\n")
                                break
                            elif 'CPU(s):' in line and 'NUMA' not in line:
                                cpu_count = line.split(':', 1)[1].strip()
                                f.write(f"CPU Count: {cpu_count}\n")
                except Exception:
                    pass
            elif shutil.which("sysctl"):  # macOS
                try:
                    cpu_result = subprocess.run(
                        ["sysctl", "-n", "machdep.cpu.brand_string"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    if cpu_result.returncode == 0:
                        f.write(f"CPU: {cpu_result.stdout.strip()}\n")
                except Exception:
                    pass
            
            # Memory information
            if Path("/proc/meminfo").exists():  # Linux
                try:
                    with open("/proc/meminfo", "r") as meminfo:
                        for line in meminfo:
                            if line.startswith("MemTotal:"):
                                mem_kb = int(line.split()[1])
                                mem_mb = mem_kb // 1024
                                mem_gb = mem_mb / 1024
                                f.write(f"RAM: {mem_mb} MB ({mem_gb:.1f} GB)\n")
                                break
                except Exception:
                    pass
            elif shutil.which("sysctl"):  # macOS
                try:
                    mem_result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    if mem_result.returncode == 0:
                        mem_bytes = int(mem_result.stdout.strip())
                        mem_mb = mem_bytes // (1024 * 1024)
                        mem_gb = mem_mb / 1024
                        f.write(f"RAM: {mem_mb} MB ({mem_gb:.1f} GB)\n")
                except Exception:
                    pass
        
        print(f"Created info file: {info_file}")


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Execute Kapper benchmarks")
    parser.add_argument("benchmark_dir", help="Path to extracted benchmark suite")
    parser.add_argument("version", help="Kapper version being tested")
    parser.add_argument("--quick", action="store_true", 
                       help="Run minimal benchmarks for fast testing (1 fork, 1 iteration, 1s runtime, no warmup)")
    
    args = parser.parse_args()
    
    benchmark_dir = Path(args.benchmark_dir).resolve()
    executor = BenchmarkExecutor()
    
    try:
        results_dir = executor.run_benchmark(benchmark_dir, args.version, quick=args.quick)
        print(f"Benchmark complete! Results available at: {results_dir}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)