from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import (  # noqa: E402
    ProfileError,
    list_profiles,
    load_profile,
    validate_editorial_profile,
)


class EditorialProfileTest(unittest.TestCase):
    def test_loads_known_profile(self) -> None:
        profile = load_profile("nine-tenths")
        self.assertEqual(profile.profile_id, "nine-tenths")
        self.assertEqual(profile.data["id"], "nine-tenths")
        self.assertIn("title", profile.data["output"]["required_fields"])

    def test_lists_only_profiles_with_editorial_contract(self) -> None:
        self.assertIn("nine-tenths", list_profiles())
        self.assertNotIn("_template", list_profiles())

    def test_unknown_profile_lists_valid_profiles(self) -> None:
        with self.assertRaisesRegex(ProfileError, "Valid profiles: nine-tenths"):
            load_profile("missing-profile")

    def test_rejects_paths_and_invalid_names(self) -> None:
        for value in ("../nine-tenths", "nine-tenths/profile.json", "C:\\temp", "NINE"):
            with self.subTest(value=value), self.assertRaises(ProfileError):
                load_profile(value)

    def test_validates_complete_structure(self) -> None:
        profile = load_profile("nine-tenths")
        broken = copy.deepcopy(profile.data)
        del broken["narrative"]["hook_rules"]
        with self.assertRaisesRegex(ProfileError, "narrative.hook_rules"):
            validate_editorial_profile(broken, expected_id="nine-tenths")

    def test_symlink_or_escape_cannot_load_arbitrary_file(self) -> None:
        profile = load_profile("nine-tenths")
        with tempfile.TemporaryDirectory() as temp:
            profiles_root = Path(temp) / "profiles"
            profiles_root.mkdir()
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "editorial-profile.json").write_text(
                json.dumps(profile.data), encoding="utf-8"
            )
            link = profiles_root / "nine-tenths"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks are unavailable on this host")
            with self.assertRaises(ProfileError):
                load_profile("nine-tenths", profiles_root=profiles_root)


if __name__ == "__main__":
    unittest.main()
