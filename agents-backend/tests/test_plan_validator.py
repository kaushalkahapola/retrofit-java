"""Tests for utils.plan_validator (Agent 3 preflight).

Loads the module by path so `utils/__init__.py` (and unidiff) is not required.
"""

import importlib.util
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
_spec = importlib.util.spec_from_file_location(
    "agents_plan_validator_test",
    _SRC / "utils" / "plan_validator.py",
)
_pv = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Required so dataclasses can resolve the module dict during class body execution.
sys.modules["agents_plan_validator_test"] = _pv
_spec.loader.exec_module(_pv)

classify_syntax_failure_message = _pv.classify_syntax_failure_message
dry_apply_plan_entries = _pv.dry_apply_plan_entries
static_validate_plan_entry = _pv.static_validate_plan_entry
validate_plan_before_apply = _pv.validate_plan_before_apply


def test_static_reject_this_assignment_before_method():
    bad = {
        "edit_type": "insert_before",
        "old_string": "    public CompletableFuture<Iterable<SysSnapshot>> currentSnapshots() {",
        "new_string": (
            "        this.clusterService = clusterService;\n"
            "    public CompletableFuture<Iterable<SysSnapshot>> currentSnapshots() {"
        ),
    }
    ok, reason = static_validate_plan_entry(bad)
    assert ok is False
    assert "this_assignment" in reason


def test_classify_syntax_statement_outside_block():
    msg = "illegal start of type\n        this.clusterService = clusterService;"
    assert classify_syntax_failure_message(msg) == "statement_outside_block"


def test_dry_apply_valid_minimal_constructor():
    src = """\
package p;
public class C {
    private int x;
    public C() {
        this.x = 1;
    }
}
"""
    entries = [
        {
            "edit_type": "replace",
            "old_string": "        this.x = 1;",
            "new_string": "        this.x = 2;",
        }
    ]
    ok, msg, out = dry_apply_plan_entries(src, entries)
    assert ok, msg
    assert "this.x = 2" in out


def test_validate_plan_preflight_catches_bad_plan():
    src = """\
package p;
public class SysSnapshots {
    public SysSnapshots() {}
    public void currentSnapshots() {
    }
}
"""
    bad_entries = [
        {
            "edit_type": "insert_before",
            "old_string": "    public void currentSnapshots() {",
            "new_string": (
                "        this.clusterService = null;\n"
                "    public void currentSnapshots() {"
            ),
        }
    ]
    pr = validate_plan_before_apply(
        plan_entries=bad_entries,
        file_content=src,
        target_file="SysSnapshots.java",
    )
    assert pr.ok is False
    assert "PLAN_STATIC_REJECT" in pr.reason or "TREE_SITTER" in pr.reason


def test_validate_plan_ok_simple_import():
    src = """\
package p;
import a.b.C;
public class T {}
"""
    entries = [
        {
            "edit_type": "insert_before",
            "old_string": "import a.b.C;",
            "new_string": "import x.y.Z;\nimport a.b.C;",
        }
    ]
    pr = validate_plan_before_apply(
        plan_entries=entries,
        file_content=src,
        target_file="T.java",
    )
    assert pr.ok is True, pr.reason


if __name__ == "__main__":
    test_validate_plan_ok_simple_import()
    test_validate_plan_preflight_catches_bad_plan()
    test_dry_apply_valid_minimal_constructor()
    test_classify_syntax_statement_outside_block()
    test_static_reject_this_assignment_before_method()
    print("test_plan_validator: all passed")
