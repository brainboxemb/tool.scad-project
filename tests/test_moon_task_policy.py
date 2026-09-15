"""Shared Moon SCAD capability policy.

Checks:
- Verification always owns the generated verification publication tree.
- Verification-SCons state remains cacheable when it exists, but is optional for
  command-only verification consumers that correctly do not create that state.
"""

from pathlib import Path

import yaml


def test_verification_scons_state_output_is_optional_glob():
    policy_path = Path(__file__).parents[1] / "moon" / "tasks" / "scad.yml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    outputs = policy["tasks"]["scad.verify"]["outputs"]

    assert "vrf/out/**" in outputs
    assert ".cache/scad-project/verification-state/**" in outputs
    assert (
        ".cache/scad-project/verification-state/last-verification-build.json"
        not in outputs
    )
