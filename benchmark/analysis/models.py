#!/usr/bin/env python3
"""
Data models for Kapper benchmark results.

Provides structured representations of JMH benchmark results and analysis data.
Supports two types of comparisons:
1. Version-to-version comparison (e.g., 1.6.1 vs 1.5.0)
2. Library comparison (Kapper vs JDBC/Hibernate/Ktorm - only for main benchmarks)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum


class BenchmarkMode(Enum):
    """JMH benchmark modes."""
    AVGT = "avgt"  # Average time
    SS = "ss"      # Single shot


class BenchmarkType(Enum):
    """Types of benchmarks in Kapper."""
    FIND_100 = "find100"
    FIND_BY_ID = "findById"
    INSERT_SINGLE_ROW = "insertSingleRow"
    SIMPLE_JOIN = "simpleJoin"
    UPDATE_SINGLE_ROW = "updateSingleRow"
    AUTO_MAPPER = "AutoMapperBenchmark"


class Library(Enum):
    """Libraries compared in benchmarks."""
    JDBC = "JDBC"
    KAPPER = "KAPPER"
    KAPPER_NO_AUTOMAP = "KAPPER-NO-AUTOMAP"
    KAPPER_RECORD = "KAPPER-RECORD"
    HIBERNATE = "HIBERNATE"
    KTORM = "KTORM"


class DatabaseType(Enum):
    """Database types used in benchmarks."""
    SQLITE = "SQLITE"
    POSTGRESQL = "POSTGRESQL"


class AutoMapperScenario(Enum):
    """AutoMapper benchmark scenarios."""
    SIMPLE_NOREFLECTION = "SIMPLE-NOREFLECTION"
    SIMPLE_DATACLASS = "SIMPLE-DATACLASS"
    SIMPLE_RECORD = "SIMPLE-RECORD"
    COMPLEX_DATACLASS = "COMPLEX-DATACLASS"
    COMPLEX_RECORD = "COMPLEX-RECORD"


@dataclass
class BenchmarkMetric:
    """Primary metric data from JMH results."""
    score: float
    score_error: Optional[float]
    score_unit: str
    score_percentiles: Dict[str, float]
    raw_data: List[List[float]]


@dataclass
class BenchmarkResult:
    """Single benchmark result from JMH output."""
    jmh_version: str
    benchmark: str
    mode: BenchmarkMode
    threads: int
    forks: int
    jvm: str
    jvm_args: List[str]
    jdk_version: str
    vm_name: str
    vm_version: str
    warmup_iterations: int
    warmup_time: str
    warmup_batch_size: int
    measurement_iterations: int
    measurement_time: str
    measurement_batch_size: int
    params: Dict[str, str]
    primary_metric: BenchmarkMetric
    secondary_metrics: Dict[str, Any]
    
    # Parsed convenience properties
    benchmark_type: Optional[BenchmarkType] = None
    library: Optional[Library] = None
    database_type: Optional[DatabaseType] = None
    scenario: Optional[AutoMapperScenario] = None
    rows: Optional[int] = None


@dataclass
class VersionResults:
    """All benchmark results for a specific Kapper version."""
    version: str
    main_avgt_results: List[BenchmarkResult]
    main_ss_results: List[BenchmarkResult]
    mapper_avgt_results: List[BenchmarkResult]
    mapper_ss_results: List[BenchmarkResult]
    info: Dict[str, str]  # From info.txt file


@dataclass
class VersionComparisonResult:
    """Result of comparing the same benchmark across two Kapper versions."""
    baseline_version: str
    comparison_version: str
    benchmark_type: BenchmarkType
    mode: BenchmarkMode
    library: Optional[Library]
    database_type: Optional[DatabaseType]
    scenario: Optional[AutoMapperScenario]
    rows: Optional[int]
    
    baseline_score: float
    comparison_score: float
    improvement_percent: float  # Positive = faster (better), Negative = slower (worse)
    improvement_ratio: float    # comparison/baseline ratio
    
    baseline_unit: str
    comparison_unit: str


@dataclass
class LibraryComparisonResult:
    """Result of comparing Kapper against other libraries within the same version."""
    version: str
    benchmark_type: BenchmarkType
    mode: BenchmarkMode
    database_type: DatabaseType
    rows: int
    
    kapper_score: float
    competitor_library: Library
    competitor_score: float
    
    kapper_advantage_percent: float  # Positive = Kapper faster, Negative = Kapper slower
    kapper_advantage_ratio: float    # competitor/kapper ratio
    
    score_unit: str


@dataclass
class VersionComparison:
    """Complete comparison between two Kapper versions."""
    baseline_version: str
    comparison_version: str
    version_comparisons: List[VersionComparisonResult]
    summary_stats: Dict[str, float]  # Overall improvements, regressions, etc.


@dataclass
class LibraryComparison:
    """Complete library comparison for a specific version."""
    version: str
    library_comparisons: List[LibraryComparisonResult]
    summary_stats: Dict[str, float]  # Overall performance vs competitors


@dataclass
class BenchmarkSuite:
    """Complete benchmark data for multiple versions."""
    versions: Dict[str, VersionResults]
    available_benchmarks: List[BenchmarkType]
    available_libraries: List[Library]
    available_databases: List[DatabaseType]
    available_scenarios: List[AutoMapperScenario]