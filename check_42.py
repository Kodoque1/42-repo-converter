#!/usr/bin/env python3
"""42 School compliance checker.

Verifies:
  - 42 header presence in .c and .h files
  - Forbidden function calls via AST (pycparser)
  - Relink detection via mtime comparison
  - Auto-update against a remote version endpoint
"""

import os
import sys
import time
import subprocess
import urllib.request

# ---------------------------------------------------------------------------
# Version & auto-update
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
UPDATE_URL = (
    "https://raw.githubusercontent.com/Kodoque1/42-repo-converter/main/VERSION"
)


def _parse_semver(version_str):
    """Return a comparable tuple from a semantic version string."""
    clean = version_str.strip().lstrip("v")
    parts = clean.split(".")
    try:
        return tuple(int(p) for p in parts[:3])
    except ValueError:
        return (0, 0, 0)


def check_version():
    """Compare the local version with a remote endpoint and warn if outdated."""
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
            remote_version = response.read().decode().strip()
        if _parse_semver(remote_version) > _parse_semver(VERSION):
            print(
                f"[UPDATE] New version available: {remote_version}"
                f" (current: {VERSION})"
            )
    except Exception:
        pass  # silent failure – connectivity is optional


# ---------------------------------------------------------------------------
# Project definitions
# ---------------------------------------------------------------------------

PROJECTS = {
    "libft": {
        "allowed_functions": [
            "malloc", "free", "write",
            "memset", "bzero", "memcpy", "memmove", "memchr", "memcmp",
            "strlen", "strlcpy", "strlcat", "strchr", "strrchr",
            "strnstr", "strncmp", "toupper", "tolower",
            "isalpha", "isdigit", "isalnum", "isascii", "isprint",
            "calloc", "strdup", "atoi",
        ],
        "make_target": "libft.a",
    },
    "ft_printf": {
        "allowed_functions": [
            "malloc", "free", "write",
            "va_start", "va_arg", "va_end", "va_copy",
        ],
        "make_target": "libftprintf.a",
    },
    "get_next_line": {
        "allowed_functions": ["malloc", "free", "read"],
        "make_target": None,
    },
    "push_swap": {
        "allowed_functions": [
            "malloc", "free", "write", "exit",
            "read",
        ],
        "make_target": "push_swap",
    },
    "so_long": {
        "allowed_functions": [
            "malloc", "free", "write", "exit", "read", "open", "close",
        ],
        "make_target": "so_long",
    },
}

# ---------------------------------------------------------------------------
# Header verification
# ---------------------------------------------------------------------------


def check_headers(files):
    """Verify that each .c / .h file contains a 42 header (``By: ``)."""
    errors = []
    for filepath in files:
        try:
            with open(filepath, "r", errors="replace") as fh:
                content = fh.read(500)
            if "By: " not in content:
                errors.append(f"Missing 42 header in: {filepath}")
        except OSError as exc:
            errors.append(f"Cannot read {filepath}: {exc}")
    return errors


# ---------------------------------------------------------------------------
# AST-based forbidden-function detection
# ---------------------------------------------------------------------------


def _build_visitor(c_ast_module):
    """Return a FuncCallVisitor class bound to the imported c_ast module."""

    class FuncCallVisitor(c_ast_module.NodeVisitor):
        def __init__(self):
            self.called_functions = set()

        def visit_FuncCall(self, node):
            if isinstance(node.name, c_ast_module.ID):
                self.called_functions.add(node.name.name)
            self.generic_visit(node)

    return FuncCallVisitor


def _preprocess(filepath):
    """Return preprocessed source for *filepath*, falling back to raw text."""
    try:
        result = subprocess.run(
            ["gcc", "-E", "-std=c99", filepath],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    with open(filepath, "r", errors="replace") as fh:
        return fh.read()


def check_forbidden_functions(c_files, allowed_functions):
    """Return a list of errors for any forbidden function call found via AST.

    Uses ``pycparser`` to build an Abstract Syntax Tree so that occurrences
    of forbidden names inside comments or string literals are *not* flagged
    (avoiding false positives from plain-text search).
    """
    try:
        from pycparser import c_parser, c_ast  # type: ignore
    except ImportError:
        print("[WARNING] pycparser not installed – skipping AST analysis.")
        return []

    FuncCallVisitor = _build_visitor(c_ast)
    parser = c_parser.CParser()
    errors = []

    for filepath in c_files:
        source = _preprocess(filepath)
        try:
            ast = parser.parse(source, filename=filepath)
        except Exception as exc:
            print(f"[WARNING] Could not parse {filepath}: {exc}")
            continue

        visitor = FuncCallVisitor()
        visitor.visit(ast)

        forbidden = visitor.called_functions - set(allowed_functions)
        for func in sorted(forbidden):
            errors.append(f"Forbidden function '{func}' called in {filepath}")

    return errors


# ---------------------------------------------------------------------------
# Relink detection
# ---------------------------------------------------------------------------


def check_relink(make_target, make_dir="."):
    """Detect unnecessary relinks by comparing *mtime* before and after make.

    Algorithm:
      1. Ensure the target exists (run make once if necessary).
      2. Record ``mtime``.
      3. Wait **1.1 s** so a genuine rebuild would produce a new timestamp.
      4. Run make again.
      5. If ``mtime`` changed, the project relinks → error.
    """
    if not make_target:
        return []

    target_path = os.path.join(make_dir, make_target)

    # Initial build if the target is absent.
    if not os.path.exists(target_path):
        print(f"[INFO] Target '{make_target}' not found – running initial make…")
        subprocess.run(["make", "-C", make_dir], capture_output=True)
        if not os.path.exists(target_path):
            return [f"make did not produce '{make_target}'"]

    mtime_before = os.path.getmtime(target_path)
    time.sleep(1.1)

    result = subprocess.run(
        ["make", "-C", make_dir], capture_output=True, text=True
    )
    if result.returncode != 0:
        return [f"make failed:\n{result.stderr.strip()}"]

    if not os.path.exists(target_path):
        return [f"'{make_target}' disappeared after rebuild"]

    mtime_after = os.path.getmtime(target_path)
    if mtime_after != mtime_before:
        return [f"Relink detected: '{make_target}' was rebuilt unnecessarily"]

    return []


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_source_files(directory="."):
    """Recursively find all .c and .h files under *directory*."""
    source_files = []
    for root, _dirs, files in os.walk(directory):
        # Skip hidden directories (e.g. .git)
        _dirs[:] = [d for d in _dirs if not d.startswith(".")]
        for fname in files:
            if fname.endswith(".c") or fname.endswith(".h"):
                source_files.append(os.path.join(root, fname))
    return source_files


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def get_project_name():
    """Read ``project.name`` from the local git config."""
    try:
        result = subprocess.run(
            ["git", "config", "project.name"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def main():
    check_version()

    project_name = get_project_name()
    if not project_name:
        print("[ERROR] git config project.name is not set.")
        sys.exit(1)

    if project_name not in PROJECTS:
        print(f"[ERROR] Unknown project '{project_name}'. Known projects: {', '.join(PROJECTS)}")
        sys.exit(1)

    project = PROJECTS[project_name]
    source_files = find_source_files(".")
    c_files = [f for f in source_files if f.endswith(".c")]

    errors = []
    errors.extend(check_headers(source_files))
    errors.extend(check_forbidden_functions(c_files, project["allowed_functions"]))
    errors.extend(check_relink(project.get("make_target")))

    if errors:
        print("[FAIL] Compliance check failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("[OK] All compliance checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
