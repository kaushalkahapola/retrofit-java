import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

try:
    from graph import route_after_recovery, route_after_structural, route_validation
except Exception:
    route_after_recovery = None
    route_after_structural = None
    route_validation = None


class TestGraphRouting(unittest.TestCase):
    def setUp(self):
        if (
            route_after_recovery is None
            or route_after_structural is None
            or route_validation is None
        ):
            self.skipTest("graph imports unavailable in this environment")

    def test_route_after_structural_routes_structural_to_recovery(self):
        state = {"patch_complexity": "STRUCTURAL"}
        self.assertEqual(route_after_structural(state), "recovery_agent")

    def test_route_after_structural_routes_rewrite_to_recovery(self):
        state = {"patch_complexity": "REWRITE"}
        self.assertEqual(route_after_structural(state), "recovery_agent")

    def test_route_after_structural_routes_trivial_to_hunk_generator(self):
        state = {"patch_complexity": "TRIVIAL"}
        self.assertEqual(route_after_structural(state), "hunk_generator")

    def test_route_after_structural_routes_empty_complexity_to_hunk_generator(self):
        state = {}
        self.assertEqual(route_after_structural(state), "hunk_generator")

    def test_validation_infra_inconclusive_ends(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "validation_infrastructure_inconclusive": True,
        }
        self.assertEqual(route_validation(state), "END")

    def test_validation_infra_category_ends(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "validation_failure_category": "test_runner_config",
        }
        self.assertEqual(route_validation(state), "END")

    def test_validation_stagnation_ends_for_non_rewrite(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "STRUCTURAL",
            "validation_repeated_patch_detected": True,
            # No failed build on record — true stagnation (e.g. tests only).
            "validation_results": {"build": {"success": True}},
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_validation_stagnation_escalates_non_rewrite_when_build_failed(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "STRUCTURAL",
            "validation_repeated_patch_detected": True,
            "validation_results": {"build": {"success": False}},
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_validation_stagnation_escalates_generation_contract_on_repeated_patch(
        self,
    ):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "STRUCTURAL",
            "validation_repeated_patch_detected": True,
            "validation_failed_stage": "generation_contract_failed",
            "validation_results": {"build": {"success": True}},
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_plan_preflight_failed_routes_as_generation_stage_not_stale_build_diag(
        self,
    ):
        """Deferred validation with plan_preflight_failed must not hit api_or_signature branch."""
        state = {
            "validation_passed": False,
            "validation_attempts": 2,
            "patch_complexity": "STRUCTURAL",
            "validation_failure_category": "context_mismatch",
            "validation_failed_stage": "plan_preflight_failed",
            "validation_results": {
                "build": {
                    "success": False,
                    "diagnostics": {
                        "issues": [
                            {"error_type": "api_or_signature_mismatch"},
                        ]
                    },
                }
            },
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_validation_stagnation_escalates_for_rewrite(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "REWRITE",
            "validation_repeated_plan_detected": True,
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_route_after_structural_routes_rewrite_blob_match_to_recovery(self):
        # REWRITE patches always route to recovery_agent regardless of match method.
        state = {
            "patch_complexity": "REWRITE",
            "structural_locator_git_match_method": "GIT_BLOB",
        }
        self.assertEqual(route_after_structural(state), "recovery_agent")

    def test_route_after_recovery_ends_on_no_fix_found(self):
        state = {
            "recovery_agent_status": "no_fix_found",
            "hunk_generation_plan": {},
        }
        self.assertEqual(route_after_recovery(state), "END")

    def test_route_after_recovery_ends_on_empty_plan(self):
        state = {
            "recovery_agent_status": "ok",
            "hunk_generation_plan": {},
        }
        self.assertEqual(route_after_recovery(state), "END")

    def test_route_after_recovery_uses_hunk_generator_for_actionable_plan(self):
        state = {
            "recovery_agent_status": "ok",
            "hunk_generation_plan": {
                "A.java": [{"old_string": "x", "new_string": "y"}]
            },
            "recovery_brief": {},
        }
        self.assertEqual(route_after_recovery(state), "hunk_generator")


if __name__ == "__main__":
    unittest.main()
