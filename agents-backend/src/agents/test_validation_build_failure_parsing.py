import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from validation_agent import _classify_build_failure


def test_classify_build_failure_extracts_files_and_errors():
    raw = """
/home/runner/temp_repo_storage/crate/server/src/main/java/io/crate/statistics/TableStats.java:68: error: cannot find symbol
    return Stats.of(unknownValue);
           ^
  symbol:   variable Stats
  location: class TableStats
/home/runner/temp_repo_storage/crate/server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java:60: error: method fromXContent in class UpdateProjection cannot be applied to given types;
"""

    category, retry_files, diagnostics, reason, build_error_files, missing_symbols = (
        _classify_build_failure(
            raw,
            known_java_files={
                "server/src/main/java/io/crate/statistics/TableStats.java",
                "server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java",
            },
        )
    )

    assert category == "context_mismatch"
    assert "server/src/main/java/io/crate/statistics/TableStats.java" in retry_files
    assert (
        "server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java"
        in retry_files
    )
    assert (
        diagnostics and diagnostics[0].get("error_type") == "api_or_signature_mismatch"
    )
    compiler_errors = diagnostics[0].get("compiler_errors") or []
    assert any("cannot find symbol" in e for e in compiler_errors)
    assert "Stats" in missing_symbols
    assert build_error_files
    assert "API/signature mismatch" in reason
