# 42-repo-converter

Easily transfer a 42 School project from a personal GitHub repo to a Vogsphere
repo — while also providing compliance-checking tools that cover the **full
42 Common Core curriculum**.

---

## Tools

### `check_42.py` — compliance checker

```bash
# Check the current project (reads git config project.name)
python3 check_42.py

# List every supported project
python3 check_42.py --list-projects

# Validate the PROJECTS dict (duplicates, missing fields, …)
python3 check_42.py --validate-projects
```

**What it checks:**

| Check | Details |
|---|---|
| 42 header | Every `.c` / `.h` file must contain `By: ` in the first 500 chars |
| Forbidden functions | AST-based detection via `pycparser` (no false positives from comments/strings) |
| Relink | Runs `make` twice; flags the project if the make target is rebuilt unnecessarily |

Set your project name once:

```bash
git config project.name libft   # or ft_printf, minishell, …
```

### `setup_42.sh` — toolchain setup

```bash
# Install the pre-push hook in the current repo
bash setup_42.sh

# Load 42clone into your shell
source setup_42.sh

# Clone a Vogsphere repo and import files from GitHub
42clone git@vogsphere.42.fr:…/myproject.git git@github.com:user/myproject.git
```

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
