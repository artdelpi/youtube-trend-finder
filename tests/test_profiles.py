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
    load_presentation_reference_analysis,
    validate_editorial_profile,
)


class EditorialProfileTest(unittest.TestCase):
    def test_loads_known_profile(self) -> None:
        profile = load_profile("possumdotmov")
        self.assertEqual(profile.profile_id, "possumdotmov")
        self.assertEqual(profile.data["id"], "possumdotmov")
        self.assertIn("title", profile.data["output"]["required_fields"])
        self.assertEqual(len(profile.data["presentation"]["archetypes"]), 5)
        self.assertEqual(
            len(profile.data["presentation_references"]["channels"]), 4
        )

    def test_loads_default_lobby_profile_with_its_own_id(self) -> None:
        profile = load_profile("possumdotmov-lobby")
        self.assertEqual(profile.profile_id, "possumdotmov-lobby")
        self.assertEqual(profile.data["id"], "possumdotmov-lobby")
        self.assertTrue(load_presentation_reference_analysis(profile)["channels"])

    def test_loads_multichannel_presentation_analysis(self) -> None:
        profile = load_profile("possumdotmov")
        analysis = load_presentation_reference_analysis(profile)
        self.assertEqual(
            {item["id"] for item in analysis["channels"]},
            {"yapmasterDV", "CericArtman", "PoppyTheory", "MrBeast"},
        )

    def test_lists_only_profiles_with_editorial_contract(self) -> None:
        self.assertIn("possumdotmov", list_profiles())
        self.assertNotIn("_template", list_profiles())

    def test_unknown_profile_lists_valid_profiles(self) -> None:
        with self.assertRaisesRegex(ProfileError, "Valid profiles: possumdotmov"):
            load_profile("missing-profile")

    def test_rejects_paths_and_invalid_names(self) -> None:
        for value in ("../possumdotmov", "possumdotmov/profile.json", "C:\\temp", "NINE"):
            with self.subTest(value=value), self.assertRaises(ProfileError):
                load_profile(value)

    def test_validates_complete_structure(self) -> None:
        profile = load_profile("possumdotmov")
        broken = copy.deepcopy(profile.data)
        del broken["narrative"]["hook_rules"]
        with self.assertRaisesRegex(ProfileError, "narrative.hook_rules"):
            validate_editorial_profile(broken, expected_id="possumdotmov")

    def test_rejects_invalid_presentation_ceiling(self) -> None:
        profile = load_profile("possumdotmov")
        broken = copy.deepcopy(profile.data)
        broken["presentation"]["archetypes"][0]["sensationalism_ceiling"] = 101
        with self.assertRaisesRegex(ProfileError, "sensationalism_ceiling"):
            validate_editorial_profile(broken, expected_id="possumdotmov")

    def test_symlink_or_escape_cannot_load_arbitrary_file(self) -> None:
        profile = load_profile("possumdotmov")
        with tempfile.TemporaryDirectory() as temp:
            profiles_root = Path(temp) / "profiles"
            profiles_root.mkdir()
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "editorial-profile.json").write_text(
                json.dumps(profile.data), encoding="utf-8"
            )
            link = profiles_root / "possumdotmov"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks are unavailable on this host")
            with self.assertRaises(ProfileError):
                load_profile("possumdotmov", profiles_root=profiles_root)


if __name__ == "__main__":
    unittest.main()
