#!/usr/bin/env python3
"""Unit tests for check_42.py – covers Features 6, 7, 8."""

import os
import sys
import tempfile
import unittest

# Allow importing check_42 from the repository root regardless of where the
# test runner is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check_42 import (
    NORMINETTE_DOCKER_IMAGE,
    PROJECTS,
    check_readme,
    check_required_paths,
    check_norminette,
    _parse_semver,
    resolve_project_name,
    _normalize_project_name,
)


# ---------------------------------------------------------------------------
# Feature 6 – README enforcement
# ---------------------------------------------------------------------------

VALID_README = """\
*This project has been created as part of the 42 curriculum by student*

## Description

A test project.

## Instructions

Run the binary.

## Resources

No AI tools were used in this project.
"""


class TestCheckReadme(unittest.TestCase):
    """Tests for check_readme()."""

    # --- hard-fail cases ---

    def test_missing_readme_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            errors, warnings = check_readme(d)
            self.assertTrue(
                any("README.md" in e for e in errors),
                "Expected a FAIL error for missing README.md",
            )
            self.assertEqual(warnings, [])

    # --- passing case ---

    def test_valid_readme_no_errors_no_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(VALID_README)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [], f"Unexpected errors: {errors}")
            self.assertEqual(warnings, [], f"Unexpected warnings: {warnings}")

    # --- warning-only cases (README.md exists) ---

    def test_missing_sections_produce_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(
                    "*This project has been created as part of the 42 curriculum by student*\n\n"
                    "No sections here.\n"
                )
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [], "Missing sections must not be a hard FAIL")
            section_warnings = [w for w in warnings if "section" in w.lower()]
            self.assertGreaterEqual(
                len(section_warnings), 3,
                "Expected warnings for Description, Instructions and Resources",
            )

    def test_non_italic_first_line_warns(self):
        with tempfile.TemporaryDirectory() as d:
            readme = (
                "This project has been created as part of the 42 curriculum by student\n\n"
                "## Description\n\nTest.\n\n"
                "## Instructions\n\nTest.\n\n"
                "## Resources\n\nNo AI used.\n"
            )
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(readme)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [], "Non-italic first line must not be a hard FAIL")
            self.assertTrue(
                any("italic" in w.lower() or "template" in w.lower() for w in warnings),
                f"Expected an italic/template warning, got: {warnings}",
            )

    def test_underscore_italic_accepted(self):
        """_..._ style italics should be accepted without a warning."""
        with tempfile.TemporaryDirectory() as d:
            readme = (
                "_This project has been created as part of the 42 curriculum by student_\n\n"
                "## Description\n\nTest.\n\n"
                "## Instructions\n\nTest.\n\n"
                "## Resources\n\nNo AI used.\n"
            )
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(readme)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [])
            italic_warnings = [
                w for w in warnings
                if "italic" in w.lower() or "template" in w.lower()
            ]
            self.assertEqual(italic_warnings, [], f"Underscore italics should not warn: {warnings}")

    def test_resources_without_ai_warns(self):
        with tempfile.TemporaryDirectory() as d:
            readme = (
                "*This project has been created as part of the 42 curriculum by student*\n\n"
                "## Description\n\nTest.\n\n"
                "## Instructions\n\nTest.\n\n"
                "## Resources\n\nSome links here.\n"
            )
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(readme)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [], "Missing AI disclosure must not be a hard FAIL")
            self.assertTrue(
                any("AI" in w or "disclosure" in w.lower() for w in warnings),
                f"Expected an AI disclosure warning, got: {warnings}",
            )

    def test_resources_with_chatgpt_no_ai_warning(self):
        with tempfile.TemporaryDirectory() as d:
            readme = (
                "*This project has been created as part of the 42 curriculum by student*\n\n"
                "## Description\n\nTest.\n\n"
                "## Instructions\n\nTest.\n\n"
                "## Resources\n\nUsed ChatGPT for debugging.\n"
            )
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(readme)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [])
            ai_warnings = [
                w for w in warnings if "AI" in w or "disclosure" in w.lower()
            ]
            self.assertEqual(ai_warnings, [], f"ChatGPT mention should satisfy AI check: {warnings}")

    def test_case_insensitive_section_headings(self):
        """Sections should be detected case-insensitively."""
        with tempfile.TemporaryDirectory() as d:
            readme = (
                "*This project has been created as part of the 42 curriculum by student*\n\n"
                "## DESCRIPTION\n\nTest.\n\n"
                "## INSTRUCTIONS\n\nTest.\n\n"
                "## RESOURCES\n\nNo AI used.\n"
            )
            with open(os.path.join(d, "README.md"), "w") as fh:
                fh.write(readme)
            errors, warnings = check_readme(d)
            self.assertEqual(errors, [])
            section_warnings = [w for w in warnings if "section" in w.lower()]
            self.assertEqual(section_warnings, [], f"Sections should be detected case-insensitively: {warnings}")


# ---------------------------------------------------------------------------
# Feature 7 – Norminette Docker image configuration
# ---------------------------------------------------------------------------

class TestNorminetteConfig(unittest.TestCase):
    """Tests for the norminette Docker image pin."""

    def test_image_constant_is_pinned(self):
        """NORMINETTE_DOCKER_IMAGE must be a non-latest pinned tag."""
        self.assertIsInstance(NORMINETTE_DOCKER_IMAGE, str)
        self.assertIn("norminette", NORMINETTE_DOCKER_IMAGE.lower())
        self.assertIn(":", NORMINETTE_DOCKER_IMAGE, "Image must include a tag")
        tag = NORMINETTE_DOCKER_IMAGE.split(":")[-1]
        self.assertNotEqual(tag, "latest", "Image tag must not be 'latest'")

    def test_norminette_skips_gracefully_without_docker(self):
        """check_norminette should skip (not raise) when Docker is absent."""
        import unittest.mock as mock
        with mock.patch(
            "subprocess.run",
            side_effect=FileNotFoundError("docker not found"),
        ):
            with tempfile.TemporaryDirectory() as d:
                dummy = os.path.join(d, "foo.c")
                with open(dummy, "w"):
                    pass
                result = check_norminette([dummy], d)
                self.assertEqual(result, [], "Should return empty list when Docker unavailable")

    def test_norminette_skips_on_empty_file_list(self):
        result = check_norminette([], ".")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Feature 8 – Required paths per project
# ---------------------------------------------------------------------------

class TestCheckRequiredPaths(unittest.TestCase):
    """Tests for check_required_paths()."""

    def test_all_paths_present_passes(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "foo.c"), "w"):
                pass
            with open(os.path.join(d, "foo.h"), "w"):
                pass
            errors = check_required_paths(d, ["foo.c", "foo.h"])
            self.assertEqual(errors, [])

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "foo.c"), "w"):
                pass
            errors = check_required_paths(d, ["foo.c", "foo.h"])
            self.assertTrue(
                any("foo.h" in e for e in errors),
                f"Expected error for missing foo.h, got: {errors}",
            )

    def test_missing_directory_fails(self):
        with tempfile.TemporaryDirectory() as d:
            errors = check_required_paths(d, ["srcs/"])
            self.assertTrue(
                any("srcs/" in e for e in errors),
                f"Expected error for missing srcs/, got: {errors}",
            )

    def test_present_directory_passes(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "srcs"))
            errors = check_required_paths(d, ["srcs/"])
            self.assertEqual(errors, [])

    def test_empty_required_paths_passes(self):
        with tempfile.TemporaryDirectory() as d:
            errors = check_required_paths(d, [])
            self.assertEqual(errors, [])

    def test_all_projects_have_required_paths(self):
        """Every PROJECTS entry must declare required_paths as a list."""
        for name, cfg in PROJECTS.items():
            self.assertIn(
                "required_paths", cfg,
                f"Project '{name}' is missing 'required_paths'",
            )
            self.assertIsInstance(
                cfg["required_paths"], list,
                f"Project '{name}' required_paths must be a list",
            )

    def test_get_next_line_required_paths(self):
        """get_next_line must require its core source files."""
        cfg = PROJECTS["get_next_line"]
        rp = cfg["required_paths"]
        self.assertIn("get_next_line.c", rp)
        self.assertIn("get_next_line.h", rp)


# ---------------------------------------------------------------------------
# Utility / regression tests
# ---------------------------------------------------------------------------

class TestUtilities(unittest.TestCase):

    def test_parse_semver(self):
        self.assertEqual(_parse_semver("1.2.3"), (1, 2, 3))
        self.assertEqual(_parse_semver("v2.0.0"), (2, 0, 0))
        self.assertEqual(_parse_semver("bad"), (0, 0, 0))

    def test_normalize_project_name(self):
        self.assertEqual(_normalize_project_name("Fract-Ol"), "fract_ol")
        self.assertEqual(_normalize_project_name("FT_PRINTF"), "ft_printf")

    def test_resolve_project_name(self):
        self.assertEqual(resolve_project_name("libft"), "libft")
        self.assertEqual(resolve_project_name("LIBFT"), "libft")
        self.assertIsNone(resolve_project_name("nonexistent_project_xyz"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
