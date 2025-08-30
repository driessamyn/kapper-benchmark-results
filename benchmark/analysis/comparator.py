#!/usr/bin/env python3
"""
Kapper Benchmark Comparator

Performs two types of comparisons:
1. Version-to-version comparison (e.g., 1.6.1 vs 1.5.0)
2. Library comparison (Kapper vs JDBC/Hibernate/Ktorm - only for main benchmarks)
"""

from typing import List, Dict, Optional, Tuple
try:
    from .models import (
        BenchmarkResult, VersionResults, BenchmarkSuite,
        VersionComparisonResult, LibraryComparisonResult,
        VersionComparison, LibraryComparison,
        BenchmarkMode, BenchmarkType, Library, DatabaseType, AutoMapperScenario
    )
except ImportError:
    from models import (
        BenchmarkResult, VersionResults, BenchmarkSuite,
        VersionComparisonResult, LibraryComparisonResult,
        VersionComparison, LibraryComparison,
        BenchmarkMode, BenchmarkType, Library, DatabaseType, AutoMapperScenario
    )


class BenchmarkComparator:
    """Compares benchmark results across versions and libraries."""
    
    def __init__(self):
        pass
    
    def compare_versions(self, baseline: VersionResults, comparison: VersionResults) -> VersionComparison:
        """Compare two Kapper versions across all benchmarks."""
        version_comparisons = []
        
        # Compare main benchmarks (AVGT only)
        main_comparisons = self._compare_main_benchmarks(
            baseline.main_avgt_results, 
            comparison.main_avgt_results,
            baseline.version,
            comparison.version
        )
        version_comparisons.extend(main_comparisons)
        
        # Compare mapper benchmarks (AVGT and SS)
        mapper_avgt_comparisons = self._compare_mapper_benchmarks(
            baseline.mapper_avgt_results,
            comparison.mapper_avgt_results,
            baseline.version,
            comparison.version,
            BenchmarkMode.AVGT
        )
        version_comparisons.extend(mapper_avgt_comparisons)
        
        mapper_ss_comparisons = self._compare_mapper_benchmarks(
            baseline.mapper_ss_results,
            comparison.mapper_ss_results,
            baseline.version,
            comparison.version,
            BenchmarkMode.SS
        )
        version_comparisons.extend(mapper_ss_comparisons)
        
        # Calculate summary statistics
        summary_stats = self._calculate_version_summary_stats(version_comparisons)
        
        return VersionComparison(
            baseline_version=baseline.version,
            comparison_version=comparison.version,
            version_comparisons=version_comparisons,
            summary_stats=summary_stats
        )
    
    def compare_libraries(self, version_results: VersionResults) -> LibraryComparison:
        """Compare Kapper against other libraries within the same version."""
        library_comparisons = []
        
        # Only compare main benchmarks (mapper benchmarks don't have library comparisons)
        main_results = version_results.main_avgt_results
        
        # Group results by benchmark type, database, and rows
        grouped_results = self._group_main_results_with_rows(main_results)
        
        for (benchmark_type, database_type, rows), results_group in grouped_results.items():
            # Find Kapper result
            kapper_result = None
            competitor_results = []
            
            for result in results_group:
                if result.library in [Library.KAPPER, Library.KAPPER_NO_AUTOMAP, Library.KAPPER_RECORD]:
                    if kapper_result is None or result.library == Library.KAPPER:
                        kapper_result = result  # Prefer KAPPER over variants
                else:
                    competitor_results.append(result)
            
            # Compare Kapper against each competitor
            if kapper_result:
                for competitor in competitor_results:
                    comparison = self._create_library_comparison(
                        version_results.version,
                        benchmark_type,
                        database_type,
                        rows,
                        kapper_result,
                        competitor
                    )
                    library_comparisons.append(comparison)
        
        # Calculate summary statistics
        summary_stats = self._calculate_library_summary_stats(library_comparisons)
        
        return LibraryComparison(
            version=version_results.version,
            library_comparisons=library_comparisons,
            summary_stats=summary_stats
        )
    
    def _compare_main_benchmarks(self, baseline_results: List[BenchmarkResult], 
                                comparison_results: List[BenchmarkResult],
                                baseline_version: str, comparison_version: str) -> List[VersionComparisonResult]:
        """Compare main benchmark results between versions."""
        comparisons = []
        
        # Group results by benchmark characteristics
        baseline_grouped = self._group_main_results(baseline_results)
        comparison_grouped = self._group_main_results(comparison_results)
        
        # Find matching benchmarks
        for key in baseline_grouped:
            if key in comparison_grouped:
                baseline_group = baseline_grouped[key]
                comparison_group = comparison_grouped[key]
                
                # Compare each library within the group
                for baseline_result in baseline_group:
                    # Find matching result in comparison
                    matching_result = next(
                        (r for r in comparison_group if r.library == baseline_result.library),
                        None
                    )
                    
                    if matching_result:
                        comparison = self._create_version_comparison(
                            baseline_result, matching_result, baseline_version, comparison_version
                        )
                        comparisons.append(comparison)
        
        return comparisons
    
    def _compare_mapper_benchmarks(self, baseline_results: List[BenchmarkResult],
                                  comparison_results: List[BenchmarkResult],
                                  baseline_version: str, comparison_version: str,
                                  mode: BenchmarkMode) -> List[VersionComparisonResult]:
        """Compare mapper benchmark results between versions."""
        comparisons = []
        
        # Group by scenario and rows
        baseline_grouped = self._group_mapper_results(baseline_results)
        comparison_grouped = self._group_mapper_results(comparison_results)
        
        # Find matching benchmarks
        for key in baseline_grouped:
            if key in comparison_grouped:
                baseline_result = baseline_grouped[key]
                comparison_result = comparison_grouped[key]
                
                comparison = VersionComparisonResult(
                    baseline_version=baseline_version,
                    comparison_version=comparison_version,
                    benchmark_type=BenchmarkType.AUTO_MAPPER,
                    mode=mode,
                    library=None,  # Not applicable for mapper benchmarks
                    database_type=None,  # Not applicable for mapper benchmarks
                    scenario=baseline_result.scenario,
                    rows=baseline_result.rows,
                    baseline_score=baseline_result.primary_metric.score,
                    comparison_score=comparison_result.primary_metric.score,
                    improvement_percent=self._calculate_improvement_percent(
                        baseline_result.primary_metric.score,
                        comparison_result.primary_metric.score
                    ),
                    improvement_ratio=comparison_result.primary_metric.score / baseline_result.primary_metric.score,
                    baseline_unit=baseline_result.primary_metric.score_unit,
                    comparison_unit=comparison_result.primary_metric.score_unit
                )
                comparisons.append(comparison)
        
        return comparisons
    
    def _group_main_results(self, results: List[BenchmarkResult]) -> Dict[Tuple, List[BenchmarkResult]]:
        """Group main benchmark results by benchmark type and database (ignore rows for version comparison)."""
        grouped = {}
        for result in results:
            key = (result.benchmark_type, result.database_type)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        return grouped
    
    def _group_main_results_with_rows(self, results: List[BenchmarkResult]) -> Dict[Tuple, List[BenchmarkResult]]:
        """Group main benchmark results by benchmark type, database, and rows (for library comparison)."""
        grouped = {}
        for result in results:
            key = (result.benchmark_type, result.database_type, result.rows)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        return grouped
    
    def _group_mapper_results(self, results: List[BenchmarkResult]) -> Dict[Tuple, BenchmarkResult]:
        """Group mapper benchmark results by scenario and rows."""
        grouped = {}
        for result in results:
            key = (result.scenario, result.rows)
            grouped[key] = result  # Only one result per scenario/rows combination
        return grouped
    
    def _create_version_comparison(self, baseline: BenchmarkResult, comparison: BenchmarkResult,
                                 baseline_version: str, comparison_version: str) -> VersionComparisonResult:
        """Create a version comparison result."""
        return VersionComparisonResult(
            baseline_version=baseline_version,
            comparison_version=comparison_version,
            benchmark_type=baseline.benchmark_type,
            mode=baseline.mode,
            library=baseline.library,
            database_type=baseline.database_type,
            scenario=baseline.scenario,
            rows=baseline.rows,
            baseline_score=baseline.primary_metric.score,
            comparison_score=comparison.primary_metric.score,
            improvement_percent=self._calculate_improvement_percent(
                baseline.primary_metric.score,
                comparison.primary_metric.score
            ),
            improvement_ratio=comparison.primary_metric.score / baseline.primary_metric.score,
            baseline_unit=baseline.primary_metric.score_unit,
            comparison_unit=comparison.primary_metric.score_unit
        )
    
    def _create_library_comparison(self, version: str, benchmark_type: BenchmarkType,
                                 database_type: DatabaseType, rows: int,
                                 kapper_result: BenchmarkResult,
                                 competitor_result: BenchmarkResult) -> LibraryComparisonResult:
        """Create a library comparison result."""
        return LibraryComparisonResult(
            version=version,
            benchmark_type=benchmark_type,
            mode=BenchmarkMode.AVGT,  # Main benchmarks are always AVGT
            database_type=database_type,
            rows=rows,
            kapper_score=kapper_result.primary_metric.score,
            competitor_library=competitor_result.library,
            competitor_score=competitor_result.primary_metric.score,
            kapper_advantage_percent=self._calculate_improvement_percent(
                competitor_result.primary_metric.score,  # Competitor as baseline
                kapper_result.primary_metric.score       # Kapper as comparison
            ),
            kapper_advantage_ratio=competitor_result.primary_metric.score / kapper_result.primary_metric.score,
            score_unit=kapper_result.primary_metric.score_unit
        )
    
    def _calculate_improvement_percent(self, baseline_score: float, comparison_score: float) -> float:
        """Calculate improvement percentage (positive = faster/better, negative = slower/worse)."""
        if baseline_score == 0:
            return 0.0
        # For time-based metrics, lower is better, so improvement is (baseline - comparison) / baseline
        return ((baseline_score - comparison_score) / baseline_score) * 100.0
    
    def _calculate_version_summary_stats(self, comparisons: List[VersionComparisonResult]) -> Dict[str, float]:
        """Calculate summary statistics for version comparison."""
        if not comparisons:
            return {}
        
        improvements = [c.improvement_percent for c in comparisons]
        
        return {
            'total_comparisons': len(comparisons),
            'improvements': len([i for i in improvements if i > 0]),
            'regressions': len([i for i in improvements if i < 0]),
            'no_change': len([i for i in improvements if i == 0]),
            'avg_improvement_percent': sum(improvements) / len(improvements),
            'max_improvement_percent': max(improvements) if improvements else 0.0,
            'max_regression_percent': min(improvements) if improvements else 0.0,
        }
    
    def _calculate_library_summary_stats(self, comparisons: List[LibraryComparisonResult]) -> Dict[str, float]:
        """Calculate summary statistics for library comparison."""
        if not comparisons:
            return {}
        
        advantages = [c.kapper_advantage_percent for c in comparisons]
        
        return {
            'total_comparisons': len(comparisons),
            'kapper_wins': len([a for a in advantages if a > 0]),
            'kapper_losses': len([a for a in advantages if a < 0]),
            'ties': len([a for a in advantages if a == 0]),
            'avg_kapper_advantage_percent': sum(advantages) / len(advantages),
            'max_kapper_advantage_percent': max(advantages) if advantages else 0.0,
            'max_kapper_disadvantage_percent': min(advantages) if advantages else 0.0,
        }


if __name__ == "__main__":
    # Test the comparator
    import sys
    from pathlib import Path
    try:
        from result_parser import ResultParser
    except ImportError:
        print("Make sure to run from the analysis directory")
        sys.exit(1)
    
    parser = ResultParser()
    comparator = BenchmarkComparator()
    
    # Test version comparison if both versions exist
    analyse_version = "1.6.1"
    compare_version = "1.5.0"
    
    # Handle different execution contexts (from analysis dir or from root)
    script_dir = Path(__file__).parent
    if (script_dir.parent / "results").exists():
        results_dir = script_dir.parent / "results"  # Running from analysis dir or root
    else:
        results_dir = Path("../results")  # Fallback
    
    print(f"Looking for results in: {results_dir.resolve()}")
    print(f"Checking if {results_dir / analyse_version} exists: {(results_dir / analyse_version).exists()}")
    print(f"Checking if {results_dir / compare_version} exists: {(results_dir / compare_version).exists()}")
    
    if (results_dir / analyse_version).exists() and (results_dir / compare_version).exists():
        print(f"Testing version comparison: {analyse_version} vs {compare_version}")
        baseline = parser.parse_version_results(results_dir / analyse_version, analyse_version)
        comparison = parser.parse_version_results(results_dir / compare_version, compare_version)

        # Debug: Check what benchmarks we have
        print(f"Baseline ({baseline.version}) main results: {len(baseline.main_avgt_results)}")
        print(f"Comparison ({comparison.version}) main results: {len(comparison.main_avgt_results)}")
        
        # Show sample benchmark keys for debugging
        if baseline.main_avgt_results:
            sample_baseline = baseline.main_avgt_results[0]
            print(f"Sample baseline key: ({sample_baseline.benchmark_type}, {sample_baseline.database_type}, {sample_baseline.rows})")
        
        if comparison.main_avgt_results:
            sample_comparison = comparison.main_avgt_results[0]
            print(f"Sample comparison key: ({sample_comparison.benchmark_type}, {sample_comparison.database_type}, {sample_comparison.rows})")
        
        version_comp = comparator.compare_versions(baseline, comparison)
        print(f"Total comparisons: {len(version_comp.version_comparisons)}")
        print(f"Summary: {version_comp.summary_stats}")
        
        # Show a few examples
        print("\nSample comparisons:")
        for i, comp in enumerate(version_comp.version_comparisons[:3]):
            print(f"  {i+1}. {comp.benchmark_type.value if comp.benchmark_type else 'Unknown'} "
                  f"({comp.library.value if comp.library else 'Unknown'}) "
                  f"- {comp.improvement_percent:.1f}% improvement")
    else:
        print(f"Skipping version comparison - one or both directories not found")
    
    # Test library comparison for both versions
    print(f"\n{'='*50}")
    print(f"Testing library comparison for {analyse_version}")
    if (results_dir / analyse_version).exists():
        baseline_results = parser.parse_version_results(results_dir / analyse_version, analyse_version)
        
        library_comp_baseline = comparator.compare_libraries(baseline_results)
        print(f"Total library comparisons: {len(library_comp_baseline.library_comparisons)}")
        print(f"Summary: {library_comp_baseline.summary_stats}")
        
        # Show a few examples
        print(f"\nSample library comparisons for {analyse_version}:")
        for i, comp in enumerate(library_comp_baseline.library_comparisons[:3]):
            print(f"  {i+1}. {comp.benchmark_type.value} vs {comp.competitor_library.value} "
                  f"- Kapper {comp.kapper_advantage_percent:.1f}% {'faster' if comp.kapper_advantage_percent > 0 else 'slower'}")
    
    print(f"\n{'='*50}")
    print(f"Testing library comparison for {compare_version}")
    if (results_dir / compare_version).exists():
        comparison_results = parser.parse_version_results(results_dir / compare_version, compare_version)
        
        library_comp_comparison = comparator.compare_libraries(comparison_results)
        print(f"Total library comparisons: {len(library_comp_comparison.library_comparisons)}")
        print(f"Summary: {library_comp_comparison.summary_stats}")
        
        # Show a few examples
        print(f"\nSample library comparisons for {compare_version}:")
        for i, comp in enumerate(library_comp_comparison.library_comparisons[:3]):
            print(f"  {i+1}. {comp.benchmark_type.value} vs {comp.competitor_library.value} "
                  f"- Kapper {comp.kapper_advantage_percent:.1f}% {'faster' if comp.kapper_advantage_percent > 0 else 'slower'}")