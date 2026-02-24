# 42-repo-converter

Compliance checker for 42 School projects — checks an existing local folder
against the rules of the **full 42 Common Core curriculum**.

---

## Tools

### `check_42.py` — compliance checker

```bash
# Check a project folder
python3 check_42.py <folder_path> <project_name>

# Examples
python3 check_42.py ~/projects/libft libft
python3 check_42.py . minishell

# List every supported project
python3 check_42.py --list-projects

# Validate the PROJECTS dict (duplicates, missing fields, …)
python3 check_42.py --validate-projects
```

**What it checks:**

| Check | Outcome | Details |
|---|---|---|
| README.md present | **FAIL** | `README.md` must exist in the project folder |
| README.md structure | **WARN** | First non-empty line should be italicized 42 template; `Description`, `Instructions`, `Resources` sections expected |
| README.md AI disclosure | **WARN** | `Resources` section should mention AI usage (keywords: AI, artificial intelligence, ChatGPT, Copilot) |
| Required files | **FAIL** | Per-project required paths must exist (e.g. `Makefile`, `libft.h`) |
| 42 header | **FAIL** | Every `.c` / `.h` file must contain `By: ` in the first 500 chars |
| Forbidden functions | **FAIL** | AST-based detection via `pycparser` (no false positives from comments/strings) |
| Relink | **FAIL** | Runs `make` twice; flags the project if the make target is rebuilt unnecessarily |

Output prefixes: `[FAIL]` = hard error (exits 1), `[WARN]` = advisory (exits 0 if no errors).

#### README.md rules

- **Mandatory (FAIL)**: `README.md` must exist in the project folder.
- **Advisory (WARN)** — the following are checked when `README.md` exists but do *not* cause a hard failure:
  - The first non-empty line should be italicized (`*…*` or `_…_`) and should
    match the 42 template sentence:
    *This project has been created as part of the 42 curriculum by …*
  - The file should contain headings for `Description`, `Instructions`, and
    `Resources` (matched case-insensitively at any heading level `#`–`######`).
  - If a `Resources` section is present it should disclose AI usage with at
    least one of the keywords: `AI`, `artificial intelligence`, `ChatGPT`, `Copilot`.

#### Norminette (CI only)

Norminette style checking is run **in CI only** and is informational — it
never fails the pipeline.  It is **not** supported in the local script.

The CI pipeline installs `norminette==3.3.51` via pip and runs it against all
fixture `.c` / `.h` files:

```yaml
- name: Install dependencies
  run: pip install pycparser norminette==3.3.51
```

#### Per-project required paths

Each project definition in `PROJECTS` includes a `required_paths` list.
To add or modify required paths for a project, edit the corresponding entry in
`check_42.py`:

```python
"libft": {
    "allowed_functions": [...],
    "make_target": "libft.a",
    "required_paths": ["Makefile", "libft.h"],  # ← edit here
},
```

Any path that is absent from the project folder causes a **FAIL**.

---

## Supported projects (full 42 Common Core)

| Rank | Project | Notes |
|------|---------|-------|
| 0 | `libft` | C standard-library re-implementation |
| 1 | `ft_printf` | Variadic output formatter |
| 1 | `get_next_line` | Line-by-line file reader |
| 1 | `born2beroot` | System administration / VM |
| 2 | `push_swap` | Sorting algorithm with limited operations |
| 2 | `pipex` | Shell pipeline (`|`) re-implementation |
| 2 | `so_long` | 2-D tile game (MinilibX) |
| 2 | `fdf` | 3-D wireframe renderer (MinilibX) |
| 2 | `fract-ol` | Fractal renderer (MinilibX) |
| 2 | `minitalk` | UNIX-signal IPC |
| 3 | `minishell` | Bash-like shell |
| 3 | `philosophers` | Dining-philosophers (pthreads) |
| 4 | `netpractice` | Network subnetting exercises |
| 4 | `cub3d` | Raycasting 3-D game (MinilibX) |
| 4 | `minirt` | Ray-tracing renderer (MinilibX) |
| 4 | `cpp00` – `cpp09` | C++ modules (no `.c` files; AST check skipped) |
| 5 | `ft_irc` | C++ IRC server |
| 5 | `inception` | Docker system administration |
| 5 | `webserv` | C++ HTTP server |
| 6 | `ft_transcendence` | Full-stack web application |

> **Tip:** Project names are matched case-insensitively and hyphens/underscores
> are treated as equivalent, so `fract-ol`, `fract_ol`, and `FRACT_OL` all
> resolve to the same entry.
