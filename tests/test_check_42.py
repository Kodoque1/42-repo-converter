#!/usr/bin/env python3
"""Unit tests for check_42.py – covers README enforcement, required paths, and utilities."""

import os
import subprocess
import sys
import tempfile
import unittest

# Allow importing check_42 from the repository root regardless of where the
# test runner is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check_42 import (
    PROJECTS,
    check_headers,
    check_readme,
    check_required_paths,
    find_source_files,
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


# ---------------------------------------------------------------------------
# find_source_files – directory-based file discovery
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestFindSourceFiles(unittest.TestCase):
    """Tests for find_source_files()."""

    def test_finds_c_and_h_files(self):
        fixture = os.path.join(FIXTURES_DIR, "get_next_line")
        files = find_source_files(fixture)
        basenames = [os.path.basename(f) for f in files]
        self.assertIn("get_next_line.c", basenames)
        self.assertIn("get_next_line.h", basenames)

    def test_does_not_return_readme(self):
        fixture = os.path.join(FIXTURES_DIR, "get_next_line")
        files = find_source_files(fixture)
        basenames = [os.path.basename(f) for f in files]
        self.assertNotIn("README.md", basenames)

    def test_empty_directory_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            files = find_source_files(d)
            self.assertEqual(files, [])

    def test_skips_hidden_directories(self):
        with tempfile.TemporaryDirectory() as d:
            hidden = os.path.join(d, ".git")
            os.makedirs(hidden)
            with open(os.path.join(hidden, "hidden.c"), "w"):
                pass
            files = find_source_files(d)
            self.assertEqual(files, [], "Files inside .git should be skipped")


# ---------------------------------------------------------------------------
# check_headers – 42 header detection
# ---------------------------------------------------------------------------


class TestCheckHeaders(unittest.TestCase):
    """Tests for check_headers()."""

    def test_fixture_files_have_headers(self):
        fixture = os.path.join(FIXTURES_DIR, "get_next_line")
        files = find_source_files(fixture)
        errors = check_headers(files)
        self.assertEqual(errors, [], f"Fixture files should all have 42 headers: {errors}")

    def test_missing_header_produces_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nohdr.c")
            with open(path, "w") as fh:
                fh.write("int main(void) { return 0; }\n")
            errors = check_headers([path])
            self.assertTrue(
                any("nohdr.c" in e for e in errors),
                f"Expected error for missing 42 header, got: {errors}",
            )

    def test_present_header_no_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "valid.c")
            with open(path, "w") as fh:
                fh.write("/* By: student <student@student.42.fr> */\nint f(void){return 0;}\n")
            errors = check_headers([path])
            self.assertEqual(errors, [], f"Expected no errors for file with 42 header: {errors}")

    def test_empty_list_returns_no_errors(self):
        errors = check_headers([])
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# main() CLI – new <folder_path> <project_name> interface
# ---------------------------------------------------------------------------


class TestMainCLI(unittest.TestCase):
    """Integration tests for the new main() CLI interface."""

    def _run(self, args):
        """Run check_42.py with the given argument list; return (returncode, stdout)."""
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "check_42.py")
        result = subprocess.run(
            [sys.executable, script] + args,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr

    def test_list_projects_exits_zero(self):
        rc, output = self._run(["--list-projects"])
        self.assertEqual(rc, 0)
        self.assertIn("libft", output)

    def test_validate_projects_exits_zero(self):
        rc, output = self._run(["--validate-projects"])
        self.assertEqual(rc, 0)
        self.assertIn("[OK]", output)

    def test_missing_args_exits_nonzero(self):
        rc, output = self._run([])
        self.assertNotEqual(rc, 0, "Should exit non-zero when no args given")
        self.assertIn("Usage:", output)

    def test_invalid_folder_exits_nonzero(self):
        rc, output = self._run(["/nonexistent/path/xyz", "libft"])
        self.assertNotEqual(rc, 0)
        self.assertIn("not found", output.lower())

    def test_unknown_project_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            rc, output = self._run([d, "totally_unknown_project_xyz"])
            self.assertNotEqual(rc, 0)
            self.assertIn("Unknown project", output)

    def test_fixture_get_next_line_passes(self):
        """The bundled get_next_line fixture must pass all checks (no make target)."""
        fixture = os.path.join(FIXTURES_DIR, "get_next_line")
        rc, output = self._run([fixture, "get_next_line"])
        self.assertEqual(rc, 0, f"Fixture should pass: {output}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
