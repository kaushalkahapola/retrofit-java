import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from graph import route_after_structural, route_validation


class TestGraphRouting(unittest.TestCase):
    def test_route_after_structural_skips_planning_for_structural(self):
        state = {"patch_complexity": "STRUCTURAL"}
        self.assertEqual(route_after_structural(state), "hunk_generator")

    def test_route_after_structural_keeps_planning_for_rewrite(self):
        state = {"patch_complexity": "REWRITE"}
        self.assertEqual(route_after_structural(state), "planning_agent")

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
        self.assertEqual(route_validation(state), "END")

    def test_validation_stagnation_escalates_non_rewrite_when_build_failed(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "STRUCTURAL",
            "validation_repeated_patch_detected": True,
            "validation_results": {"build": {"success": False}},
        }
        self.assertEqual(route_validation(state), "planning_agent")

    def test_validation_stagnation_escalates_generation_contract_on_repeated_patch(self):
        state = {
            "validation_passed": False,
            "validation_attempts": 1,
            "patch_complexity": "STRUCTURAL",
            "validation_repeated_patch_detected": True,
            "validation_failed_stage": "generation_contract_failed",
            "validation_results": {"build": {"success": True}},
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

    def test_route_after_structural_downgrades_blob_match(self):
        state = {
            "patch_complexity": "REWRITE",
            "structural_locator_git_match_method": "GIT_BLOB",
        }
        self.assertEqual(route_after_structural(state), "hunk_generator")


if __name__ == "__main__":
    unittest.main()
