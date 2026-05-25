"""Dead Code Detection — static-analysis guard against unused code.

Three independent checks (one test each):

  1. Unused public symbols — top-level functions / classes / constants that no
     module ever *loads* (AST reference analysis, not substring regex).
  2. Orphaned modules — source modules never imported by any other module.
  3. Unreachable code — statements directly following return/raise/break/continue.

Division of labour with the linter (do not duplicate it here):
  - ruff `F` already owns within-file unused imports / locals / redefinitions.
  - ruff `ERA` already owns commented-out code.
  This test owns the *cross-file* gaps (1, 2) plus unreachable code (3), for
  which no ruff rule is currently enabled.

Maintain the exception sets in CONFIG when a symbol/module is intentionally
unreferenced (public API for external consumers, framework-invoked, etc.).

Limitations (conservative by design — favours avoiding false positives so a
failure always means real dead code):
  - Name matching is unqualified: if any module loads a same-named symbol, the
    definition counts as referenced. This can mask a genuinely-dead symbol that
    shares a name used elsewhere, but never deletes live code by mistake.
  - Only module-level defs are checked (not methods or class attributes).

Run:  uv run pytest tests/test_dead_code.py -q
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# ─── Configuration (per-project) ───────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]

# Where first-party source lives, and the base directory module names are
# computed against. For a `src/`-as-package layout these differ from a
# `src/<pkg>/` layout — keep them in sync with the import style used in code.
SRC_DIR = ROOT / "src"
MODULE_BASE = ROOT  # module names are relative to here -> "src.pipeline.extract"
IMPORT_ROOT = "src"  # first-party import prefix

# Directories scanned for *references* in addition to source: any place a
# symbol might legitimately be used. .py files are parsed (AST); other files
# are searched as text so symbols used only in templates/prompts/configs aren't
# flagged (e.g. LLM prompt markdown under src/pipeline/prompts/).
REFERENCE_PY_DIRS = [SRC_DIR, ROOT / "tests"]
REFERENCE_TEXT_FILES = [ROOT / "pyproject.toml", *SRC_DIR.rglob("*.md")]

SKIP_DIR_NAMES = {"__pycache__", ".venv", ".git", ".mypy_cache", ".ruff_cache"}

# Modules invoked via console-scripts / frameworks, never imported by name.
MODULE_EXCEPTIONS = {
    "src.cli",  # console_scripts entry point (src.cli:main)
}

# Public symbols intentionally unreferenced internally (external API, reflection,
# etc.). Format: "module::name". Document *why* on each line.
SYMBOL_EXCEPTIONS: set[str] = {
    # Protocol seam for a future EmbeddingMatcher (see module docstring + ROADMAP);
    # GrepMatcher implements it structurally, so it has no internal call site.
    "src.search.matcher::Matcher",
}

# Decorator attribute names that mark a function as framework-invoked and thus
# legitimately never imported by name: @app.command(), @queue_app.command(...).
FRAMEWORK_DECORATORS = {"command", "callback"}

MIN_NAME_LEN = 4  # shorter identifiers have a high false-positive rate

# Per-check toggles.
CHECK_UNUSED_SYMBOLS = True
CHECK_ORPHANED_MODULES = True
CHECK_UNREACHABLE = True

# ─── File discovery ─────────────────────────────────────────────────────────


def _iter_py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob("*.py") if not SKIP_DIR_NAMES.intersection(path.parts)
    )


def _module_name(path: Path) -> str:
    rel = path.relative_to(MODULE_BASE).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _source_modules() -> dict[str, Path]:
    return {_module_name(p): p for p in _iter_py_files(SRC_DIR)}


# ─── Symbol & reference extraction (AST) ────────────────────────────────────


def _is_framework_decorated(node: ast.AST) -> bool:
    decorators = getattr(node, "decorator_list", [])
    for dec in decorators:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in FRAMEWORK_DECORATORS:
            return True
        if isinstance(target, ast.Name) and target.id in FRAMEWORK_DECORATORS:
            return True
    return False


def _public_definitions(path: Path) -> list[tuple[str, int]]:
    """Top-level public functions, classes, and constants in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    definitions: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_") or _is_framework_decorated(node):
                continue
            definitions.append((node.name, node.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    definitions.append((target.id, node.lineno))
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                definitions.append((target.id, node.lineno))
    return definitions


def _loaded_names(path: Path) -> set[str]:
    """Every name that is *read* in a module (Name loads + attribute accesses)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


# ─── Import resolution (orphaned-module check) ──────────────────────────────


def _resolve_import_from(
    current_module: str, is_package_module: bool, node: ast.ImportFrom
) -> str | None:
    if node.level == 0:
        return node.module
    if not current_module:
        return None
    current_parts = current_module.split(".")
    if not is_package_module:
        current_parts = current_parts[:-1]
    keep = len(current_parts) - (node.level - 1)
    if keep <= 0:
        return node.module
    base_parts = current_parts[:keep]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _imported_modules(path: Path, modules: dict[str, Path]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    current_module = _module_name(path)
    is_package_module = path.name == "__init__.py"
    imported: set[str] = set()

    def add_if_known(name: str) -> None:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            candidate = ".".join(parts[:i])
            if candidate in modules:
                imported.add(candidate)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(IMPORT_ROOT):
                    add_if_known(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(current_module, is_package_module, node)
            if not base or not base.startswith(IMPORT_ROOT):
                continue
            add_if_known(base)
            for alias in node.names:
                if alias.name != "*":
                    add_if_known(f"{base}.{alias.name}")

    imported.discard(current_module)
    return imported


# ─── Unreachable-code detection (AST) ───────────────────────────────────────

_TERMINALS = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _unreachable_lines(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[int] = []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for index, stmt in enumerate(block[:-1]):
                if isinstance(stmt, _TERMINALS):
                    hits.append(block[index + 1].lineno)
                    break
    return sorted(hits)


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_no_unused_public_symbols() -> None:
    if not CHECK_UNUSED_SYMBOLS:
        return

    modules = _source_modules()
    reference_files = sorted({p for d in REFERENCE_PY_DIRS for p in _iter_py_files(d)})
    loaded_by_file = {p: _loaded_names(p) for p in reference_files}
    text_corpus = "\n".join(
        f.read_text(encoding="utf-8") for f in REFERENCE_TEXT_FILES if f.exists()
    )

    findings: list[tuple[str, str, int]] = []
    for module, path in modules.items():
        for name, lineno in _public_definitions(path):
            if len(name) < MIN_NAME_LEN:
                continue
            if f"{module}::{name}" in SYMBOL_EXCEPTIONS:
                continue
            # A symbol is alive if any module loads it — including its own, since
            # the definition statement itself is not a load. Dead = never read
            # anywhere. (Conservative: shared names mask deadness but never cause
            # a live symbol to be flagged.)
            if any(name in names for names in loaded_by_file.values()):
                continue
            if re.search(rf"\b{re.escape(name)}\b", text_corpus):
                continue
            findings.append((module, name, lineno))

    if findings:
        report = "\n".join(
            f"  {module}::{name}  (line {lineno})" for module, name, lineno in sorted(findings)
        )
        raise AssertionError(
            f"Found {len(findings)} unused public symbol(s) referenced by no other "
            f"module.\nEither remove the dead code or add to SYMBOL_EXCEPTIONS:\n{report}"
        )


def test_no_orphaned_modules() -> None:
    if not CHECK_ORPHANED_MODULES:
        return

    modules = _source_modules()
    importers = sorted({p for d in REFERENCE_PY_DIRS for p in _iter_py_files(d)})
    incoming: dict[str, int] = dict.fromkeys(modules, 0)
    for path in importers:
        for imported in _imported_modules(path, modules):
            if imported in incoming:
                incoming[imported] += 1

    orphaned = [
        module
        for module, refs in sorted(incoming.items())
        if refs == 0
        and module not in MODULE_EXCEPTIONS
        and modules[module].name != "__init__.py"  # packages aggregate, don't originate
    ]

    if orphaned:
        report = "\n".join(f"  {module}" for module in orphaned)
        raise AssertionError(
            f"Found {len(orphaned)} orphaned module(s) imported by nothing.\n"
            f"Either remove or add to MODULE_EXCEPTIONS:\n{report}"
        )


def test_no_unreachable_code() -> None:
    if not CHECK_UNREACHABLE:
        return

    findings: list[str] = []
    for module, path in sorted(_source_modules().items()):
        for lineno in _unreachable_lines(path):
            findings.append(f"  {module}:{lineno}")

    if findings:
        report = "\n".join(findings)
        raise AssertionError(
            f"Found {len(findings)} unreachable statement(s) after "
            f"return/raise/break/continue:\n{report}"
        )
