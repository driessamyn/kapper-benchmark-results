#!/usr/bin/env python3
"""
Kapper Benchmark Result Parser

Parses JMH JSON outputs into structured data models.
Handles both main benchmark results (AVGT only) and mapper results (AVGT + SS for cold start).
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
try:
    from .models import (
        BenchmarkResult, BenchmarkMetric, BenchmarkMode, BenchmarkType,
        Library, DatabaseType, AutoMapperScenario, VersionResults
    )
except ImportError:
    from models import (
        BenchmarkResult, BenchmarkMetric, BenchmarkMode, BenchmarkType,
        Library, DatabaseType, AutoMapperScenario, VersionResults
    )


class ResultParser:
    """Parses JMH benchmark results into structured data."""
    
    def __init__(self):
        self.benchmark_type_patterns = {
            BenchmarkType.FIND_100: r'find100',
            BenchmarkType.FIND_BY_ID: r'findById',
            BenchmarkType.INSERT_SINGLE_ROW: r'insertSingleRow',
            BenchmarkType.SIMPLE_JOIN: r'simpleJoin',
            BenchmarkType.UPDATE_SINGLE_ROW: r'updateSingleRow',
            BenchmarkType.AUTO_MAPPER: r'AutoMapperBenchmark',
        }
    
    def parse_jmh_json(self, json_path: Path) -> List[BenchmarkResult]:
        """Parse a single JMH JSON file into BenchmarkResult objects."""
        if not json_path.exists():
            return []
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        results = []
        for item in data:
            try:
                result = self._parse_single_result(item)
                results.append(result)
            except Exception as e:
                print(f"Warning: Failed to parse result in {json_path}: {e}")
                continue
        
        return results
    
    def _parse_single_result(self, data: Dict[str, Any]) -> BenchmarkResult:
        """Parse a single JMH result object."""
        # Parse primary metric
        primary_metric_data = data.get('primaryMetric', {})
        primary_metric = BenchmarkMetric(
            score=primary_metric_data.get('score', 0.0),
            score_error=self._parse_float_or_nan(primary_metric_data.get('scoreError')),
            score_unit=primary_metric_data.get('scoreUnit', ''),
            score_percentiles=primary_metric_data.get('scorePercentiles', {}),
            raw_data=primary_metric_data.get('rawData', [])
        )
        
        # Create base result
        result = BenchmarkResult(
            jmh_version=data.get('jmhVersion', ''),
            benchmark=data.get('benchmark', ''),
            mode=BenchmarkMode(data.get('mode', 'avgt')),
            threads=data.get('threads', 1),
            forks=data.get('forks', 1),
            jvm=data.get('jvm', ''),
            jvm_args=data.get('jvmArgs', []),
            jdk_version=data.get('jdkVersion', ''),
            vm_name=data.get('vmName', ''),
            vm_version=data.get('vmVersion', ''),
            warmup_iterations=data.get('warmupIterations', 0),
            warmup_time=data.get('warmupTime', ''),
            warmup_batch_size=data.get('warmupBatchSize', 1),
            measurement_iterations=data.get('measurementIterations', 1),
            measurement_time=data.get('measurementTime', ''),
            measurement_batch_size=data.get('measurementBatchSize', 1),
            params=data.get('params', {}),
            primary_metric=primary_metric,
            secondary_metrics=data.get('secondaryMetrics', {})
        )
        
        # Parse additional metadata
        self._parse_benchmark_metadata(result)
        
        return result
    
    def _parse_benchmark_metadata(self, result: BenchmarkResult):
        """Parse benchmark type, library, database, etc. from the benchmark name and params."""
        benchmark_name = result.benchmark
        params = result.params
        
        # Determine benchmark type
        for bench_type, pattern in self.benchmark_type_patterns.items():
            if re.search(pattern, benchmark_name, re.IGNORECASE):
                result.benchmark_type = bench_type
                break
        
        # Parse AutoMapper scenario
        if result.benchmark_type == BenchmarkType.AUTO_MAPPER:
            scenario_str = params.get('scenario', '')
            try:
                result.scenario = AutoMapperScenario(scenario_str)
            except ValueError:
                print(f"Unknown AutoMapper scenario: {scenario_str}")
            
            # For mapper benchmarks, numberOfResults parameter
            try:
                result.rows = int(params.get('numberOfResults', 0))
            except (ValueError, TypeError):
                pass
        
        else:
            # Parse main benchmark metadata from benchmark name
            # Format: net.samyn.kapper.benchmark.BenchmarkSuite.benchmarkName
            
            # Extract library from params first, then benchmark name patterns
            library_param = params.get('library', '').upper()
            if library_param:
                try:
                    # Handle special cases
                    if library_param == 'KAPPER-NO-AUTOMAP':
                        result.library = Library.KAPPER_NO_AUTOMAP
                    elif library_param == 'KAPPER-RECORD':
                        result.library = Library.KAPPER_RECORD
                    else:
                        result.library = Library(library_param)
                except ValueError:
                    print(f"Unknown library parameter: {library_param}")
            
            # Fallback: Extract library from benchmark name patterns
            if not result.library:
                if 'JDBC' in benchmark_name:
                    result.library = Library.JDBC
                elif 'HIBERNATE' in benchmark_name:
                    result.library = Library.HIBERNATE
                elif 'KTORM' in benchmark_name:
                    result.library = Library.KTORM
                elif 'KAPPER-RECORD' in benchmark_name:
                    result.library = Library.KAPPER_RECORD
                elif 'KAPPER-NO-AUTOMAP' in benchmark_name:
                    result.library = Library.KAPPER_NO_AUTOMAP
                elif 'KAPPER' in benchmark_name:
                    result.library = Library.KAPPER
            
            # Extract database type from params or benchmark name
            db_param = params.get('databaseType', '').upper()
            if db_param:
                try:
                    result.database_type = DatabaseType(db_param)
                except ValueError:
                    print(f"Unknown database type: {db_param}")
            
            # Extract rows from params
            rows_param = params.get('rows', params.get('numberOfRows', ''))
            if rows_param:
                try:
                    result.rows = int(rows_param)
                except (ValueError, TypeError):
                    pass
    
    def _parse_float_or_nan(self, value: Any) -> Optional[float]:
        """Parse a float value that might be 'NaN' string."""
        if value is None or value == 'NaN':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def parse_info_file(self, info_path: Path) -> Dict[str, str]:
        """Parse info.txt file into a dictionary."""
        if not info_path.exists():
            return {}
        
        info = {}
        try:
            with open(info_path, 'r') as f:
                content = f.read()
                
                # Extract key information using regex patterns
                patterns = {
                    'jar_file': r'JMH benchmark JAR: ([^\s]+)',
                    'jar_sha256': r'SHA-256: ([a-f0-9]+)',
                    'kapper_version': r'Kapper version: ([^\n]+)',
                    'java_version': r'java version "([^"]+)"',
                    'cpu': r'CPU: ([^\n]+)',
                    'ram': r'RAM: ([^\n]+)',
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, content)
                    if match:
                        info[key] = match.group(1).strip()
                
                # Store full content as well
                info['full_content'] = content
                
        except Exception as e:
            print(f"Warning: Failed to parse info file {info_path}: {e}")
        
        return info
    
    def parse_version_results(self, results_dir: Path, version: str) -> VersionResults:
        """Parse all results for a specific version.
        
        Main benchmarks only have AVGT mode (average time).
        Mapper benchmarks have both AVGT and SS (single shot for cold start).
        """
        
        # Try different file naming conventions
        # New format: main-results-avgt.json, mapper-results-avgt.json
        main_avgt_path = results_dir / "main-results-avgt.json"
        mapper_avgt_path = results_dir / "mapper-results-avgt.json"
        mapper_ss_path = results_dir / "mapper-results-ss.json"
        
        # Legacy format: results-avgt.json (contains main benchmarks)
        if not main_avgt_path.exists():
            legacy_avgt_path = results_dir / "results-avgt.json"
            if legacy_avgt_path.exists():
                main_avgt_path = legacy_avgt_path
        
        info_path = results_dir / "info.txt"
        
        main_avgt_results = self.parse_jmh_json(main_avgt_path)
        mapper_avgt_results = self.parse_jmh_json(mapper_avgt_path)
        mapper_ss_results = self.parse_jmh_json(mapper_ss_path)  # Cold start scenarios
        info = self.parse_info_file(info_path)
        
        # Filter out any AutoMapper results from main results (in case files were mixed up)
        filtered_main_results = []
        for result in main_avgt_results:
            if result.benchmark_type != BenchmarkType.AUTO_MAPPER:
                filtered_main_results.append(result)
        
        return VersionResults(
            version=version,
            main_avgt_results=filtered_main_results,
            main_ss_results=[],  # Not applicable for main benchmarks
            mapper_avgt_results=mapper_avgt_results,
            mapper_ss_results=mapper_ss_results,
            info=info
        )


if __name__ == "__main__":
    # Example usage
    import sys
    from pathlib import Path
    
    if len(sys.argv) != 3:
        print("Usage: python result_parser.py <results_dir> <version>")
        sys.exit(1)
    
    results_dir = Path(sys.argv[1])
    version = sys.argv[2]
    
    parser = ResultParser()
    version_results = parser.parse_version_results(results_dir, version)
    
    print(f"Parsed results for Kapper {version}:")
    print(f"  Main AVGT results: {len(version_results.main_avgt_results)}")
    print(f"  Mapper AVGT results: {len(version_results.mapper_avgt_results)}")
    print(f"  Mapper SS results: {len(version_results.mapper_ss_results)} (cold start)")
    
    # Show some sample data
    if version_results.main_avgt_results:
        print(f"\n  Sample main result:")
        result = version_results.main_avgt_results[0]
        print(f"    Benchmark: {result.benchmark}")
        print(f"    Library: {result.library}")
        print(f"    Database: {result.database_type}")
        print(f"    Score: {result.primary_metric.score} {result.primary_metric.score_unit}")
    
    if version_results.mapper_avgt_results:
        print(f"\n  Sample mapper result:")
        result = version_results.mapper_avgt_results[0]
        print(f"    Benchmark: {result.benchmark}")
        print(f"    Scenario: {result.scenario}")
        print(f"    Score: {result.primary_metric.score} {result.primary_metric.score_unit}")