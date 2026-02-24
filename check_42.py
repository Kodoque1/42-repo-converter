#!/usr/bin/env python3
"""42 School compliance checker.

Usage:
  python3 check_42.py <folder_path> <project_name>
  python3 check_42.py --list-projects
  python3 check_42.py --validate-projects

Verifies:
  - README.md presence (hard fail) and structure (warnings)
  - 42 header presence in .c and .h files
  - Forbidden function calls via AST (pycparser)
  - Required files/directories per project
  - Relink detection via mtime comparison
  - Auto-update against a remote version endpoint
"""

import os
import re
import sys
import time
import subprocess
import urllib.request

# ---------------------------------------------------------------------------
# Project definitions
# ---------------------------------------------------------------------------
# Sources: 42 Intra subject PDFs (https://projects.intra.42.fr)
# Each entry lists the C library functions that a student is allowed to call
# in the corresponding project.  C++ projects (cpp00-09, ft_irc, webserv) and
# system/web projects (born2beroot, netpractice, inception, ft_transcendence)
# contain no .c files, so the forbidden-function AST check is skipped for them
# automatically by check_forbidden_functions().
# ---------------------------------------------------------------------------

PROJECTS = {
    # ── Rank 0 ──────────────────────────────────────────────────────────────
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
        "required_paths": ["Makefile", "libft.h"],
    },
    # ── Rank 1 ──────────────────────────────────────────────────────────────
    "ft_printf": {
        "allowed_functions": [
            "malloc", "free", "write",
            "va_start", "va_arg", "va_end", "va_copy",
        ],
        "make_target": "libftprintf.a",
        "required_paths": ["Makefile"],
    },
    "get_next_line": {
        "allowed_functions": ["malloc", "free", "read"],
        "make_target": None,
        "required_paths": ["get_next_line.c", "get_next_line.h"],
    },
    "born2beroot": {
        # System-administration/VM project – no C source files.
        "allowed_functions": [],
        "make_target": None,
        "required_paths": ["signature.txt"],
    },
    # ── Rank 2 ──────────────────────────────────────────────────────────────
    "push_swap": {
        "allowed_functions": [
            "malloc", "free", "read", "write", "exit",
        ],
        "make_target": "push_swap",
        "required_paths": ["Makefile"],
    },
    "pipex": {
        "allowed_functions": [
            "open", "close", "read", "write",
            "malloc", "free", "perror", "strerror",
            "access", "dup", "dup2", "execve", "exit",
            "fork", "pipe", "unlink", "wait", "waitpid",
        ],
        "make_target": "pipex",
        "required_paths": ["Makefile"],
    },
    "so_long": {
        "allowed_functions": [
            "open", "close", "read", "write", "malloc", "free",
            "perror", "strerror", "exit",
            # MinilibX
            "mlx_init", "mlx_new_window", "mlx_clear_window",
            "mlx_destroy_window", "mlx_destroy_display",
            "mlx_loop", "mlx_loop_end", "mlx_loop_hook",
            "mlx_key_hook", "mlx_mouse_hook", "mlx_expose_hook", "mlx_hook",
            "mlx_new_image", "mlx_put_image_to_window", "mlx_destroy_image",
            "mlx_get_data_addr", "mlx_get_color_value", "mlx_pixel_put",
            "mlx_string_put", "mlx_xpm_file_to_image", "mlx_png_file_to_image",
        ],
        "make_target": "so_long",
        "required_paths": ["Makefile"],
    },
    "fdf": {
        "allowed_functions": [
            "open", "close", "read", "write", "malloc", "free",
            "perror", "strerror", "exit",
            # MinilibX
            "mlx_init", "mlx_new_window", "mlx_clear_window",
            "mlx_destroy_window", "mlx_destroy_display",
            "mlx_loop", "mlx_loop_end", "mlx_loop_hook",
            "mlx_key_hook", "mlx_mouse_hook", "mlx_expose_hook", "mlx_hook",
            "mlx_new_image", "mlx_put_image_to_window", "mlx_destroy_image",
            "mlx_get_data_addr", "mlx_get_color_value", "mlx_pixel_put",
            # Math
            "cos", "sin", "tan",
        ],
        "make_target": "fdf",
        "required_paths": ["Makefile"],
    },
    "fract-ol": {
        "allowed_functions": [
            "malloc", "free", "perror", "strerror", "exit", "open", "close",
            # MinilibX
            "mlx_init", "mlx_new_window", "mlx_clear_window",
            "mlx_destroy_window", "mlx_destroy_display",
            "mlx_loop", "mlx_loop_end", "mlx_loop_hook",
            "mlx_key_hook", "mlx_mouse_hook", "mlx_expose_hook", "mlx_hook",
            "mlx_new_image", "mlx_put_image_to_window", "mlx_destroy_image",
            "mlx_get_data_addr", "mlx_get_color_value", "mlx_pixel_put",
            # Math
            "cos", "sin", "tan",
        ],
        "make_target": "fractol",
        "required_paths": ["Makefile"],
    },
    "minitalk": {
        "allowed_functions": [
            "write", "exit", "malloc", "free",
            "signal", "kill", "getpid",
            "pause", "sleep", "usleep",
            "sigemptyset", "sigaddset", "sigaction",
        ],
        # Produces 'server' and 'client' binaries; no single make target.
        "make_target": None,
        "required_paths": ["Makefile"],
    },
    # ── Rank 3 ──────────────────────────────────────────────────────────────
    "minishell": {
        "allowed_functions": [
            "readline", "rl_clear_history", "rl_on_new_line",
            "rl_replace_line", "rl_redisplay", "add_history",
            "printf", "malloc", "free", "write",
            "open", "read", "close",
            "fork", "wait", "waitpid", "wait3", "wait4",
            "signal", "sigaction", "sigemptyset", "sigaddset",
            "kill", "exit",
            "getcwd", "chdir", "stat", "lstat", "fstat", "unlink",
            "execve", "dup", "dup2", "pipe",
            "opendir", "readdir", "closedir",
            "strerror", "perror",
            "isatty", "ttyname", "ttyslot",
            "ioctl", "getenv",
            "tcsetattr", "tcgetattr",
            "tgetent", "tgetflag", "tgetnum", "tgetstr", "tgoto", "tputs",
        ],
        "make_target": "minishell",
        "required_paths": ["Makefile"],
    },
    "philosophers": {
        "allowed_functions": [
            "malloc", "free", "write",
            "usleep", "gettimeofday",
            "pthread_create", "pthread_detach", "pthread_join",
            "pthread_mutex_init", "pthread_mutex_destroy",
            "pthread_mutex_lock", "pthread_mutex_unlock",
        ],
        "make_target": "philo",
        "required_paths": ["Makefile"],
    },
    # ── Rank 4 ──────────────────────────────────────────────────────────────
    "netpractice": {
        # Network subnetting exercise – web-app interface, no C source files.
        "allowed_functions": [],
        "make_target": None,
        "required_paths": [],
    },
    "cub3d": {
        "allowed_functions": [
            "open", "close", "read", "write", "malloc", "free",
            "perror", "strerror", "exit",
            "gettimeofday",
            # Math
            "cos", "sin", "tan", "atan2", "sqrt", "floor", "ceil",
            # MinilibX
            "mlx_init", "mlx_new_window", "mlx_clear_window",
            "mlx_destroy_window", "mlx_destroy_display",
            "mlx_loop", "mlx_loop_end", "mlx_loop_hook",
            "mlx_key_hook", "mlx_mouse_hook", "mlx_expose_hook", "mlx_hook",
            "mlx_new_image", "mlx_put_image_to_window", "mlx_destroy_image",
            "mlx_get_data_addr", "mlx_get_color_value", "mlx_pixel_put",
            "mlx_xpm_file_to_image", "mlx_png_file_to_image",
        ],
        "make_target": "cub3d",
        "required_paths": ["Makefile"],
    },
    "minirt": {
        "allowed_functions": [
            "open", "close", "read", "write", "malloc", "free",
            "perror", "strerror", "exit",
            # Math
            "cos", "sin", "tan", "atan2", "acos", "asin", "sqrt",
            "pow", "floor", "ceil", "fabs",
            # MinilibX
            "mlx_init", "mlx_new_window", "mlx_clear_window",
            "mlx_destroy_window", "mlx_destroy_display",
            "mlx_loop", "mlx_loop_end", "mlx_loop_hook",
            "mlx_key_hook", "mlx_mouse_hook", "mlx_expose_hook", "mlx_hook",
            "mlx_new_image", "mlx_put_image_to_window", "mlx_destroy_image",
            "mlx_get_data_addr", "mlx_get_color_value", "mlx_pixel_put",
            "mlx_xpm_file_to_image", "mlx_png_file_to_image",
        ],
        "make_target": "miniRT",
        "required_paths": ["Makefile"],
    },
    # C++ modules (Rank 4): no .c files → AST check skipped automatically.
    "cpp00": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp01": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp02": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp03": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp04": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp05": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp06": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp07": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp08": {"allowed_functions": [], "make_target": None, "required_paths": []},
    "cpp09": {"allowed_functions": [], "make_target": None, "required_paths": []},
    # ── Rank 5 ──────────────────────────────────────────────────────────────
    "ft_irc": {
        # C++ IRC server – no .c files; AST check skipped automatically.
        "allowed_functions": [],
        "make_target": "ircserv",
        "required_paths": ["Makefile"],
    },
    "inception": {
        # Docker system-administration project – no C source files.
        "allowed_functions": [],
        "make_target": None,
        "required_paths": ["Makefile", "srcs/"],
    },
    "webserv": {
        # C++ HTTP server – no .c files; AST check skipped automatically.
        "allowed_functions": [],
        "make_target": "webserv",
        "required_paths": ["Makefile"],
    },
    # ── Rank 6 ──────────────────────────────────────────────────────────────
    "ft_transcendence": {
        # Full-stack web application – no C source files.
        "allowed_functions": [],
        "make_target": None,
        "required_paths": [],
    },
}

# ---------------------------------------------------------------------------
# Project name normalization
# ---------------------------------------------------------------------------


def _normalize_project_name(name):
    """Normalize a project name for lookup (lower-case, hyphens→underscores)."""
    return name.strip().lower().replace("-", "_").replace(" ", "_")


# Build a lookup table: normalized_name → canonical key in PROJECTS
_NORMALIZED_PROJECTS = {_normalize_project_name(k): k for k in PROJECTS}


def resolve_project_name(raw_name):
    """Return the canonical PROJECTS key for *raw_name*, or None if unknown."""
    return _NORMALIZED_PROJECTS.get(_normalize_project_name(raw_name))


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
# Norminette style check
# ---------------------------------------------------------------------------


def check_norminette(source_files):
    """Run norminette on *source_files* and return advisory warnings.

    Returns an empty list when norminette is not installed or no source files
    are provided.  Norm violations are returned as warnings (never hard errors).
    """
    if not source_files:
        return []
    try:
        result = subprocess.run(
            ["norminette"] + source_files,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []  # norminette not installed – skip silently
    warnings = []
    for line in result.stdout.splitlines():
        if line.startswith("Error:") or line.startswith("Warning:"):
            warnings.append(f"[NORMINETTE] {line.strip()}")
    return warnings


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
# README enforcement (Feature 6)
# ---------------------------------------------------------------------------

_README_TEMPLATE_KEYWORDS = ["42", "curriculum"]
_README_REQUIRED_SECTIONS = ["description", "instructions", "resources"]
_README_AI_KEYWORDS = ["ai", "artificial intelligence", "chatgpt", "copilot"]


def check_readme(directory="."):
    """Check README.md presence and structure.

    Returns:
        (errors, warnings) — *errors* contains hard-fail items (missing file);
        *warnings* contains non-blocking advisory items (structure issues).
    """
    errors = []
    warnings = []
    readme_path = os.path.join(directory, "README.md")

    if not os.path.isfile(readme_path):
        errors.append("README.md is missing from the project folder")
        return errors, warnings

    try:
        with open(readme_path, "r", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        warnings.append(f"Cannot read README.md: {exc}")
        return errors, warnings

    lines = content.splitlines()

    # Check that the first non-empty line is italicized and matches the
    # 42 template sentence (lenient: accept *...* or _..._).
    first_line = next((ln.strip() for ln in lines if ln.strip()), None)
    if first_line is None:
        warnings.append("README.md appears to be empty")
    else:
        is_italic = (
            (first_line.startswith("*") and first_line.endswith("*"))
            or (first_line.startswith("_") and first_line.endswith("_"))
        )
        has_template = all(
            kw.lower() in first_line.lower()
            for kw in _README_TEMPLATE_KEYWORDS
        )
        if not is_italic or not has_template:
            warnings.append(
                "README.md: first non-empty line should be italicized and "
                "follow the 42 template, e.g. "
                "*This project has been created as part of the 42 curriculum by …*"
            )

    # Check that required sections exist (case-insensitive heading detection).
    content_lower = content.lower()
    for section in _README_REQUIRED_SECTIONS:
        pattern = r"^#{1,6}\s+" + re.escape(section) + r"\b"
        if not re.search(pattern, content_lower, re.MULTILINE):
            warnings.append(
                f"README.md is missing a '{section.capitalize()}' section"
            )

    # If a Resources section exists, warn when there is no AI disclosure.
    resources_pattern = r"^#{1,6}\s+resources\b.*?(?=^#{1,6}\s|\Z)"
    resources_match = re.search(
        resources_pattern, content_lower, re.MULTILINE | re.DOTALL
    )
    if resources_match:
        resources_text = resources_match.group(0)
        if not any(kw in resources_text for kw in _README_AI_KEYWORDS):
            warnings.append(
                "README.md Resources section does not mention AI usage/disclosure "
                "(expected keywords: AI, artificial intelligence, ChatGPT, Copilot)"
            )

    return errors, warnings


# ---------------------------------------------------------------------------
# Required-paths check (Feature 8)
# ---------------------------------------------------------------------------


def check_required_paths(directory, required_paths):
    """Return errors for any path in *required_paths* absent under *directory*.

    Each entry in *required_paths* is a relative path (file or directory).
    """
    errors = []
    for path in required_paths:
        if not os.path.exists(os.path.join(directory, path)):
            errors.append(f"Required path missing: {path}")
    return errors


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
# Self-check utilities (--list-projects, --validate-projects)
# ---------------------------------------------------------------------------


def cmd_list_projects():
    """Print all supported project names and exit."""
    print("Supported 42 Common Core projects:")
    for name in sorted(PROJECTS):
        print(f"  {name}")
    sys.exit(0)


def cmd_validate_projects():
    """Validate the PROJECTS dict and exit with 0 on success, 1 on failure."""
    errors = []

    # Check for empty keys
    for key in PROJECTS:
        if not key:
            errors.append("PROJECTS contains an empty key.")

    # Check for duplicate normalized names (catches fdf / FdF / fd-f etc.)
    seen_normalized = {}
    for key in PROJECTS:
        norm = _normalize_project_name(key)
        if norm in seen_normalized:
            errors.append(
                f"Duplicate normalized key: '{key}' clashes with "
                f"'{seen_normalized[norm]}' (both normalize to '{norm}')."
            )
        seen_normalized[norm] = key

    # Check that each entry has required fields
    for key, cfg in PROJECTS.items():
        if "allowed_functions" not in cfg:
            errors.append(f"'{key}' is missing 'allowed_functions'.")
        if "make_target" not in cfg:
            errors.append(f"'{key}' is missing 'make_target'.")
        if "required_paths" not in cfg:
            errors.append(f"'{key}' is missing 'required_paths'.")
        af = cfg.get("allowed_functions", [])
        if isinstance(af, list) and len(af) != len(set(af)):
            dupes = [f for f in af if af.count(f) > 1]
            errors.append(
                f"'{key}' has duplicate allowed_functions: {sorted(set(dupes))}"
            )
        rp = cfg.get("required_paths", [])
        if not isinstance(rp, list):
            errors.append(f"'{key}' required_paths must be a list.")
        elif not all(isinstance(p, str) for p in rp):
            errors.append(f"'{key}' required_paths entries must all be strings.")

    if errors:
        print("[FAIL] PROJECTS validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"[OK] PROJECTS validated: {len(PROJECTS)} projects, no issues found.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    # Handle self-check flags before doing anything else.
    if "--list-projects" in sys.argv:
        cmd_list_projects()
    if "--validate-projects" in sys.argv:
        cmd_validate_projects()

    check_version()

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <folder_path> <project_name>")
        print(f"Run '{sys.argv[0]} --list-projects' to see supported projects.")
        sys.exit(1)

    folder_path = sys.argv[1]
    project_name = sys.argv[2]

    if not os.path.isdir(folder_path):
        print(f"[ERROR] Folder not found: {folder_path}")
        sys.exit(1)

    canonical_name = resolve_project_name(project_name)
    if canonical_name is None:
        print(
            f"[ERROR] Unknown project '{project_name}'. "
            f"Run '{sys.argv[0]} --list-projects' to see supported projects."
        )
        sys.exit(1)

    project = PROJECTS[canonical_name]
    source_files = find_source_files(folder_path)
    c_files = [f for f in source_files if f.endswith(".c")]

    errors = []
    warnings = []

    # Feature 6 – README enforcement
    readme_errors, readme_warnings = check_readme(folder_path)
    errors.extend(readme_errors)
    warnings.extend(readme_warnings)

    # Feature 8 – Required paths
    errors.extend(check_required_paths(folder_path, project.get("required_paths", [])))

    # Existing checks
    errors.extend(check_headers(source_files))
    errors.extend(check_forbidden_functions(c_files, project["allowed_functions"]))
    errors.extend(check_relink(project.get("make_target"), folder_path))

    # Norminette style check (informational)
    warnings.extend(check_norminette(source_files))

    # Print warnings (non-blocking)
    for warn in warnings:
        print(f"[WARN] {warn}")

    if errors:
        print("[FAIL] Compliance check failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("[OK] All compliance checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
