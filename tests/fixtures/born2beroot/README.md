# born2beroot

System-administration project — no C source files.

This fixture validates that `check_42.py` correctly handles projects with no
`.c` or `.h` files: the header check and forbidden-function AST scan are both
skipped, and the absence of a `make_target` means the relink check is also
skipped.  The script should exit 0 (all checks pass).
