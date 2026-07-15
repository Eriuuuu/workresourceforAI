from dataclasses import dataclass, field
from pathlib import Path

from tester_toolbox.config.settings import DEFAULT_LOCATE_TIMEOUT_SECONDS


@dataclass(frozen=True)
class PackageInfo:
    index: int
    source: str
    product: str
    date: str
    package_name: str
    archive_name: str
    author: str = ""
    sdk_commit: str = ""
    product_commit: str = ""
    local_archive: Path | None = None
    extract_dir: Path | None = None


@dataclass(frozen=True)
class PerformancePoint:
    script_name: str
    point_name: str
    point_type: str = "time"
    standard_name: str = "platform"
    threshold: float | None = None

    @property
    def key(self):
        return f"{self.script_name}\u0001{self.point_name}\u0001{self.point_type}"


@dataclass(frozen=True)
class RegressionStandard:
    name: str
    threshold: float | None = None


@dataclass
class LocateRequest:
    package_sources: list[str]
    performance_points: list[PerformancePoint]
    tests_path: Path
    workspace: Path
    run_count: int = 1
    timeout_seconds: int = DEFAULT_LOCATE_TIMEOUT_SECONDS
    mp_flag: str = "0"
    standard_mode: str = "platform"
    standards: dict[str, RegressionStandard] = field(default_factory=dict)


@dataclass
class FunctionalLocateRequest:
    package_sources: list[str]
    collection_ini: Path
    section_names: list[str]
    tests_path: Path
    workspace: Path
    timeout_seconds: int = DEFAULT_LOCATE_TIMEOUT_SECONDS
    mp_flag: str = "0"


@dataclass
class PackageRunResult:
    package: PackageInfo
    script_name: str
    result_log_path: Path
    points: dict[str, dict]


@dataclass
class PackageFunctionalRunResult:
    package: PackageInfo
    collection_ini: Path
    result_log_path: Path
    failed_sections: set[str]
