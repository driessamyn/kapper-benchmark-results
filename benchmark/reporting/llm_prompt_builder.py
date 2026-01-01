#!/usr/bin/env python3
"""
Kapper Benchmark LLM Prompt Builder

Creates structured prompts for LLM analysis of benchmark results.
Generates prompts that provide context, data, and specific analysis questions
for AI-powered performance analysis and insights.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

# Handle imports for both standalone and module usage
try:
    from ..analysis.models import (
        VersionResults, VersionComparison, LibraryComparison,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )
    from ..analysis.result_parser import ResultParser
    from ..analysis.comparator import BenchmarkComparator
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    from analysis.models import (
        VersionResults, VersionComparison, LibraryComparison,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )
    from analysis.result_parser import ResultParser
    from analysis.comparator import BenchmarkComparator


class LLMPromptBuilder:
    """Builds structured prompts for LLM analysis of benchmark results."""
    
    def __init__(self, output_dir: Path = Path("reports")):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize analysis components
        self.parser = ResultParser()
        self.comparator = BenchmarkComparator()
    
    def build_performance_analysis_prompt(self, baseline_version: str, comparison_version: str,
                                        results_dir: Path = Path("results")) -> str:
        """Build a comprehensive prompt for LLM performance analysis."""
        
        # Load and analyze data
        baseline_results = self._load_version_results(results_dir, baseline_version)
        comparison_results = self._load_version_results(results_dir, comparison_version)
        
        if not baseline_results or not comparison_results:
            raise RuntimeError(f"Could not load results for {baseline_version} or {comparison_version}")
        
        version_comparison = self.comparator.compare_versions(baseline_results, comparison_results)
        baseline_library_comp = self.comparator.compare_libraries(baseline_results)
        comparison_library_comp = self.comparator.compare_libraries(comparison_results)
        
        # Build the prompt
        prompt_sections = []
        
        # Context and role definition
        prompt_sections.append(self._build_context_section())
        
        # Data summary
        prompt_sections.append(self._build_data_summary_section(
            baseline_results, comparison_results, version_comparison,
            baseline_library_comp, comparison_library_comp
        ))
        
        # Specific analysis tasks
        prompt_sections.append(self._build_analysis_tasks_section(
            version_comparison, baseline_library_comp, comparison_library_comp
        ))
        
        # Output format requirements
        prompt_sections.append(self._build_output_format_section())
        
        return "\n\n".join(prompt_sections)
    
    def build_technical_investigation_prompt(self, baseline_version: str, comparison_version: str,
                                           results_dir: Path = Path("results")) -> str:
        """Build a prompt focused on technical investigation of performance changes."""
        
        # Load data
        baseline_results = self._load_version_results(results_dir, baseline_version)
        comparison_results = self._load_version_results(results_dir, comparison_version)
        version_comparison = self.comparator.compare_versions(baseline_results, comparison_results)
        
        prompt_sections = []
        
        # Technical analysis context
        prompt_sections.append("""# Technical Performance Analysis Request

You are a senior performance engineer analyzing JMH benchmark results for Kapper, a Kotlin SQL mapping library. 
Your task is to conduct a deep technical investigation of performance changes between versions.

## Technical Context
- Kapper is a Kotlin library for SQL-to-object mapping
- Alternatives analyzed: JDBC (raw), Hibernate (JPA), Ktorm (Kotlin SQL DSL)
- JMH (Java Microbenchmark Harness) provides microsecond-precision measurements
- Operations: find100, findById, insertSingleRow, simpleJoin, updateSingleRow
- Databases: SQLite, PostgreSQL""")
        
        # Detailed technical data
        prompt_sections.append(self._build_technical_data_section(version_comparison))
        
        # Technical investigation questions
        prompt_sections.append(self._build_technical_questions_section(version_comparison))
        
        # Technical output requirements
        prompt_sections.append(self._build_technical_output_section())
        
        return "\n\n".join(prompt_sections)
    
    def save_prompt(self, prompt_content: str, prompt_type: str, 
                   baseline_version: str, comparison_version: str) -> Path:
        """Save a prompt to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_prompt_{prompt_type}_{baseline_version}_vs_{comparison_version}_{timestamp}.md"
        prompt_path = self.output_dir / filename
        
        with open(prompt_path, 'w') as f:
            f.write(prompt_content)
        
        return prompt_path
    
    def _load_version_results(self, results_dir: Path, version: str) -> Optional[VersionResults]:
        """Load benchmark results for a specific version."""
        version_path = results_dir / version
        if not version_path.exists():
            alt_path = results_dir / f"{version}/01"
            if alt_path.exists():
                version_path = alt_path
            else:
                return None
        
        try:
            return self.parser.parse_version_results(version_path, version)
        except Exception as e:
            print(f"Error loading {version}: {e}")
            return None
    
    def _build_context_section(self) -> str:
        """Build the context and role definition section."""
        return """# Kapper Benchmark Performance Analysis

You are an expert performance analyst specializing in database ORM and SQL mapping libraries. 
You have been asked to analyze benchmark results comparing different versions of Kapper, 
a Kotlin SQL mapping library, against its competitors.

## Background
- **Kapper**: A Kotlin library for mapping SQL query results to Kotlin objects
- **Competitors**: JDBC (raw), Hibernate (JPA standard), Ktorm (Kotlin SQL DSL)
- **Benchmarks**: JMH (Java Microbenchmark Harness) providing microsecond precision
- **Operations**: Database CRUD operations across different scenarios
- **Databases**: SQLite (embedded) and PostgreSQL (client-server)

## Your Expertise
You understand:
- JVM performance characteristics and JIT compilation
- Database connection overhead and query optimization
- Object mapping performance patterns
- SQL generation and execution costs
- Memory allocation and garbage collection impacts"""
    
    def _build_data_summary_section(self, baseline_results: VersionResults,
                                  comparison_results: VersionResults,
                                  version_comparison: VersionComparison,
                                  baseline_library_comp: LibraryComparison,
                                  comparison_library_comp: LibraryComparison) -> str:
        """Build the data summary section."""
        section = ["## Benchmark Data Summary"]
        
        # Version information
        section.append(f"**Versions Analyzed**: {baseline_results.version} (baseline) vs {comparison_results.version} (comparison)")
        section.append("")
        
        # Data availability
        section.append("**Data Availability**:")
        section.append(f"- Baseline main benchmarks: {len(baseline_results.main_avgt_results)}")
        section.append(f"- Comparison main benchmarks: {len(comparison_results.main_avgt_results)}")
        section.append(f"- Baseline mapper benchmarks: {len(baseline_results.mapper_avgt_results)} AVGT, {len(baseline_results.mapper_ss_results)} SS")
        section.append(f"- Comparison mapper benchmarks: {len(comparison_results.mapper_avgt_results)} AVGT, {len(comparison_results.mapper_ss_results)} SS")
        section.append("")
        
        # Version comparison summary
        stats = version_comparison.summary_stats
        if stats:
            section.append("**Version Comparison Summary**:")
            section.append(f"- Total comparisons: {stats.get('total_comparisons', 0)}")
            section.append(f"- Improvements: {stats.get('improvements', 0)}")
            section.append(f"- Regressions: {stats.get('regressions', 0)}")
            section.append(f"- Average change: {stats.get('avg_improvement_percent', 0):+.1f}%")
            section.append(f"- Best improvement: {stats.get('max_improvement_percent', 0):+.1f}%")
            section.append(f"- Worst regression: {stats.get('max_regression_percent', 0):+.1f}%")
            section.append("")
        
        # Library competitive position
        baseline_stats = baseline_library_comp.summary_stats
        comparison_stats = comparison_library_comp.summary_stats
        
        if baseline_stats and comparison_stats:
            section.append("**Competitive Position Changes**:")
            baseline_wins = baseline_stats.get('kapper_wins', 0)
            baseline_total = baseline_stats.get('total_comparisons', 1)
            comparison_wins = comparison_stats.get('kapper_wins', 0)
            comparison_total = comparison_stats.get('total_comparisons', 1)
            
            baseline_rate = (baseline_wins / baseline_total) * 100
            comparison_rate = (comparison_wins / comparison_total) * 100
            
            section.append(f"- {baseline_results.version}: {baseline_rate:.0f}% win rate ({baseline_wins}/{baseline_total})")
            section.append(f"- {comparison_results.version}: {comparison_rate:.0f}% win rate ({comparison_wins}/{comparison_total})")
            section.append(f"- Change: {comparison_rate - baseline_rate:+.0f} percentage points")
            section.append("")
        
        return "\n".join(section)
    
    def _build_analysis_tasks_section(self, version_comparison: VersionComparison,
                                    baseline_library_comp: LibraryComparison,
                                    comparison_library_comp: LibraryComparison) -> str:
        """Build the analysis tasks section."""
        section = ["## Analysis Tasks"]
        
        section.append("Please analyze the following aspects:")
        section.append("")
        
        section.append("### 1. Version Performance Evolution")
        section.append("- Identify the most significant performance improvements and regressions")
        section.append("- Analyze patterns by operation type (find100, findById, etc.)")
        section.append("- Consider database-specific changes (SQLite vs PostgreSQL)")
        section.append("- Examine Kapper variant performance (KAPPER, KAPPER-NO-AUTOMAP, KAPPER-RECORD)")
        section.append("")
        
        section.append("### 2. Competitive Analysis")
        section.append("- Assess how Kapper's competitive position changed between versions")
        section.append("- Identify operations where Kapper gained or lost ground vs competitors")
        section.append("- Analyze the trade-offs between different Kapper configurations")
        section.append("")
        
        section.append("### 3. Technical Insights")
        section.append("- Hypothesize potential technical reasons for major changes")
        section.append("- Consider JVM/Kotlin language improvements, library optimizations, or architectural changes")
        section.append("- Identify any concerning performance regressions that need investigation")
        section.append("")
        
        section.append("### 4. Strategic Recommendations")
        section.append("- Recommend areas for further performance investigation")
        section.append("- Suggest benchmarking improvements or additional test scenarios")
        section.append("- Provide guidance on Kapper configuration choices for optimal performance")
        section.append("")
        
        # Include specific data for analysis
        section.append("## Detailed Performance Data")
        section.append("")
        section.append("### Version Comparison Results")
        section.append("```")
        
        # Add top improvements and regressions
        improvements = [c for c in version_comparison.version_comparisons if c.improvement_percent > 0]
        regressions = [c for c in version_comparison.version_comparisons if c.improvement_percent < 0]
        
        if improvements:
            section.append("Top Improvements:")
            improvements_sorted = sorted(improvements, key=lambda x: x.improvement_percent, reverse=True)[:10]
            for comp in improvements_sorted:
                benchmark = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
                library = comp.library.value if comp.library else 'Unknown'
                section.append(f"  {benchmark} ({library}): {comp.improvement_percent:+.1f}% "
                             f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} us/op)")
        
        if regressions:
            section.append("\nTop Regressions:")
            regressions_sorted = sorted(regressions, key=lambda x: x.improvement_percent)[:10]
            for comp in regressions_sorted:
                benchmark = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
                library = comp.library.value if comp.library else 'Unknown'
                section.append(f"  {benchmark} ({library}): {comp.improvement_percent:+.1f}% "
                             f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} us/op)")
        
        section.append("```")
        section.append("")
        
        return "\n".join(section)
    
    def _build_output_format_section(self) -> str:
        """Build the output format requirements section."""
        return """## Required Output Format

Please structure your analysis as follows:

### Executive Summary
- 2-3 sentences summarizing the key findings
- Overall performance trend and competitive position change

### Key Findings
1. **Performance Evolution**
   - Most significant improvements (with quantified impact)
   - Most concerning regressions (with quantified impact)
   - Patterns by operation type or database

2. **Competitive Analysis**
   - Changes in win rate vs competitors
   - Operations where Kapper improved/declined vs alternatives
   - Relative positioning assessment

3. **Technical Hypotheses**
   - Potential root causes for major changes
   - Technical factors that might explain the patterns
   - Areas requiring deeper investigation

### Recommendations
1. **Immediate Actions**
   - Performance regressions requiring investigation
   - Configuration recommendations

2. **Strategic Considerations**
   - Long-term performance strategy suggestions
   - Benchmarking improvements

3. **Further Analysis**
   - Additional data needed
   - Suggested follow-up investigations

### Risk Assessment
- Rate the overall performance change (Low/Medium/High impact)
- Identify any critical performance regressions
- Assess competitive positioning risks"""
    
    def _build_technical_data_section(self, version_comparison: VersionComparison) -> str:
        """Build detailed technical data section."""
        section = ["## Technical Performance Data"]
        
        # Detailed breakdown by benchmark and library
        section.append("### Detailed Results by Operation")
        section.append("")
        
        # Group by benchmark type
        by_benchmark = {}
        for comp in version_comparison.version_comparisons:
            bench_type = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
            if bench_type not in by_benchmark:
                by_benchmark[bench_type] = []
            by_benchmark[bench_type].append(comp)
        
        for benchmark, comparisons in by_benchmark.items():
            section.append(f"#### {benchmark}")
            section.append("```")
            for comp in sorted(comparisons, key=lambda x: x.improvement_percent, reverse=True):
                lib = comp.library.value if comp.library else 'Unknown'
                db = comp.database_type.value if comp.database_type else 'Unknown'
                section.append(f"{lib} ({db}): {comp.baseline_score:.1f} → {comp.comparison_score:.1f} us/op "
                             f"({comp.improvement_percent:+.1f}%)")
            section.append("```")
            section.append("")
        
        return "\n".join(section)
    
    def _build_technical_questions_section(self, version_comparison: VersionComparison) -> str:
        """Build technical investigation questions."""
        section = ["## Technical Investigation Questions"]
        
        section.append("Focus your analysis on these technical aspects:")
        section.append("")
        
        section.append("1. **JVM and Runtime Performance**")
        section.append("   - Are there patterns suggesting JIT compilation changes?")
        section.append("   - Could Kotlin version upgrades explain performance shifts?")
        section.append("   - Any evidence of memory allocation or GC impact changes?")
        section.append("")
        
        section.append("2. **SQL and Database Interaction**")
        section.append("   - Do database-specific patterns suggest query optimization changes?")
        section.append("   - Are there differences in connection handling or prepared statement usage?")
        section.append("   - Could JDBC driver changes be a factor?")
        section.append("")
        
        section.append("3. **Mapping and Reflection**")
        section.append("   - How do KAPPER vs KAPPER-NO-AUTOMAP results compare?")
        section.append("   - Are there patterns in KAPPER-RECORD performance (if available)?")
        section.append("   - Could reflection or code generation changes explain the differences?")
        section.append("")
        
        section.append("4. **Library Architecture**")
        section.append("   - Are certain operations more affected than others?")
        section.append("   - Do single-row vs multi-row operations show different patterns?")
        section.append("   - Could internal caching or optimization changes be involved?")
        section.append("")
        
        return "\n".join(section)
    
    def _build_technical_output_section(self) -> str:
        """Build technical output format requirements."""
        return """## Technical Analysis Output

Provide a detailed technical report with:

### Performance Root Cause Analysis
- Technical hypothesis for each major performance change
- Evidence supporting each hypothesis
- Confidence level in each assessment

### Database-Specific Analysis
- SQLite vs PostgreSQL performance patterns
- Database-specific optimization opportunities
- Connection and query execution insights

### Library Architecture Assessment
- Impact of different Kapper configurations
- Mapping strategy performance implications
- Reflection vs code generation trade-offs

### JVM Performance Considerations
- JIT compilation and warmup implications
- Memory allocation and GC considerations
- Kotlin/JVM version impact assessment

### Actionable Technical Recommendations
- Specific code areas to investigate
- Performance tuning opportunities
- Architecture improvements to consider
- Testing and measurement enhancements

### Risk Mitigation
- Critical performance regressions to address immediately
- Monitoring recommendations for production
- Fallback strategies for performance issues"""


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate LLM prompts for benchmark analysis")
    parser.add_argument("baseline_version", help="Baseline version (e.g., 1.5.0)")
    parser.add_argument("comparison_version", help="Comparison version (e.g., 1.6.1)")
    parser.add_argument("--prompt-type", choices=["performance", "technical"], default="performance",
                       help="Type of prompt to generate")
    parser.add_argument("--results-dir", default="results", help="Results directory path")
    parser.add_argument("--output-dir", default="reports", help="Output directory for prompts")
    
    args = parser.parse_args()
    
    builder = LLMPromptBuilder(output_dir=Path(args.output_dir))
    
    try:
        if args.prompt_type == "performance":
            prompt = builder.build_performance_analysis_prompt(
                args.baseline_version, args.comparison_version, Path(args.results_dir)
            )
        else:
            prompt = builder.build_technical_investigation_prompt(
                args.baseline_version, args.comparison_version, Path(args.results_dir)
            )
        
        prompt_path = builder.save_prompt(
            prompt, args.prompt_type, args.baseline_version, args.comparison_version
        )
        print(f"LLM prompt generated: {prompt_path}")
        
    except Exception as e:
        print(f"Error generating prompt: {e}")
        sys.exit(1)