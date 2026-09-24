#!/usr/bin/env python3
"""Bundle a marked PyGameKit project as a native desktop application.

PyInstaller builds for the operating system on which it is run. Use Windows to
produce an ``.exe``, macOS to produce a macOS app, and Linux for a Linux build.
The project is staged as an internal ``game_src`` package so its existing
``PROJECT_ROOT``/``TOOLKIT_ROOT`` path convention keeps working when frozen.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_MARKER = ".pygamekit-project"
PACKAGE_NAME = "game_src"
DEFAULT_ENTRY = "main.py"
PYTHON_SUFFIX = ".py"

LAUNCHER_TEMPLATE = '''"""Generated PyGameKit bundle entry point."""

import sys
from pathlib import Path

GAME_ROOT = Path(__file__).resolve().parent / "game_src"
if str(GAME_ROOT) not in sys.path:
    sys.path.insert(0, str(GAME_ROOT))

from {module_name} import main


if __name__ == "__main__":
    main()
'''


class BundleError(ValueError):
    """Raised when a project cannot be safely bundled."""


@dataclass(frozen=True)
class BundlePlan:
    toolkit_root: Path
    project_root: Path
    app_name: str
    entry: str
    dist_dir: Path
    onefile: bool
    console: bool
    include_bitmaps: bool
    icon: Path | None
    hidden_imports: tuple[str, ...]


def find_marked_projects(toolkit_root: Path) -> list[Path]:
    """Return directly nested project directories with valid marker files."""
    return sorted(
        marker.parent.resolve()
        for marker in toolkit_root.glob(f"*/{PROJECT_MARKER}")
        if marker.is_file()
    )


def resolve_project(toolkit_root: Path, requested: str | None) -> Path:
    """Resolve an explicit project or require one unambiguous active project."""
    if requested:
        candidate = Path(requested).expanduser()
        if not candidate.is_absolute():
            candidate = toolkit_root / candidate
        project_root = candidate.resolve()
        if not (project_root / PROJECT_MARKER).is_file():
            raise BundleError(
                f"Project has no {PROJECT_MARKER} marker: {project_root}"
            )
        return project_root

    projects = find_marked_projects(toolkit_root)
    if not projects:
        raise BundleError(
            "No marked PyGameKit project found. Run bootstrap.py first or pass "
            "--project PATH."
        )
    if len(projects) > 1:
        choices = "\n".join(f"  - {path}" for path in projects)
        raise BundleError(
            "Multiple marked projects found; select one with --project PATH:\n"
            f"{choices}"
        )
    return projects[0]


def load_manifest(project_root: Path) -> dict:
    """Load and minimally validate a project's generated inventory."""
    marker = project_root / PROJECT_MARKER
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleError(f"Project marker not found: {marker}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(
            f"Invalid JSON in {marker} at line {exc.lineno}: {exc.msg}"
        ) from exc

    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise BundleError(f"Invalid file inventory in {marker}")
    for category in ("code", "assets", "bitmaps", "other"):
        if not isinstance(manifest["files"].get(category), list):
            raise BundleError(f"Missing file category {category!r} in {marker}")
    return manifest


def safe_project_path(project_root: Path, relative_name: str) -> Path:
    """Resolve one inventory path while rejecting traversal outside the project."""
    project_root = project_root.resolve()
    relative = Path(relative_name)
    if relative.is_absolute():
        raise BundleError(f"Inventory path must be relative: {relative_name}")
    resolved = (project_root / relative).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise BundleError(f"Inventory path escapes the project: {relative_name}") from exc
    if not resolved.is_file():
        raise BundleError(f"Inventory file is missing: {resolved}")
    return resolved


def sanitize_app_name(value: str) -> str:
    """Create a portable executable/folder name."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    if not name:
        raise BundleError("Application name must contain a letter or number")
    return name


def entry_module_name(entry: str) -> str:
    """Translate a Python entry path into its staged package module name."""
    path = Path(entry)
    if path.is_absolute() or path.suffix.lower() != PYTHON_SUFFIX:
        raise BundleError("--entry must be a relative .py file")
    if any(part in ("", ".", "..") for part in path.parts):
        raise BundleError("--entry cannot contain empty, '.' or '..' path parts")
    module_parts = path.with_suffix("").parts
    if not all(part.isidentifier() for part in module_parts):
        raise BundleError("Every --entry path component must be a Python identifier")
    return ".".join((PACKAGE_NAME, *module_parts))


def validate_entry(entry_path: Path) -> None:
    """Require a callable-style main function for the generated launcher."""
    try:
        tree = ast.parse(entry_path.read_text(encoding="utf-8"), filename=str(entry_path))
    except (OSError, SyntaxError) as exc:
        raise BundleError(f"Cannot parse entry point {entry_path}: {exc}") from exc
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main" for node in tree.body):
        raise BundleError(f"Entry point must define main(): {entry_path}")


def stage_project(
    project_root: Path,
    manifest: dict,
    stage_root: Path,
    entry: str = DEFAULT_ENTRY,
) -> tuple[Path, Path]:
    """Copy Python sources into an importable package and generate a launcher."""
    package_root = stage_root / PACKAGE_NAME
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")

    staged_python_files = set()
    for relative_name in manifest["files"]["code"]:
        source = safe_project_path(project_root, relative_name)
        if source.suffix.lower() != PYTHON_SUFFIX:
            continue
        relative = Path(relative_name)
        if relative.name.startswith("test_") or relative.name.endswith("_test.py"):
            continue
        destination = package_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged_python_files.add(relative.as_posix())

        parent = destination.parent
        while parent != package_root:
            init_file = parent / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")
            parent = parent.parent

    normalized_entry = Path(entry).as_posix()
    if normalized_entry not in staged_python_files:
        raise BundleError(f"Entry point is not inventoried Python code: {entry}")
    validate_entry(package_root / normalized_entry)

    launcher = stage_root / "pygamekit_launcher.py"
    launcher.write_text(
        LAUNCHER_TEMPLATE.format(module_name=entry_module_name(entry)),
        encoding="utf-8",
    )
    return launcher, package_root


def collect_data_files(
    toolkit_root: Path,
    project_root: Path,
    manifest: dict,
    include_bitmaps: bool,
) -> list[tuple[Path, str]]:
    """Return source/destination pairs for PyInstaller data collection."""
    shaders = toolkit_root / "shaders"
    if not shaders.is_dir():
        raise BundleError(f"Shared shader directory not found: {shaders}")
    data_files = [(shaders.resolve(), "shaders")]

    categories = ["assets", "other"]
    if include_bitmaps:
        categories.append("bitmaps")
    non_python_code = [
        name
        for name in manifest["files"]["code"]
        if Path(name).suffix.lower() != PYTHON_SUFFIX
    ]
    project_files = non_python_code
    for category in categories:
        project_files.extend(manifest["files"][category])

    seen = set()
    for relative_name in project_files:
        if relative_name in seen:
            continue
        seen.add(relative_name)
        source = safe_project_path(project_root, relative_name)
        relative_parent = Path(relative_name).parent.as_posix()
        destination = PACKAGE_NAME
        if relative_parent != ".":
            destination = f"{PACKAGE_NAME}/{relative_parent}"
        data_files.append((source, destination))
    return data_files


def make_pyinstaller_command(
    plan: BundlePlan,
    stage_root: Path,
    launcher: Path,
    data_files: list[tuple[Path, str]],
) -> list[str]:
    """Create the deterministic PyInstaller invocation for a bundle plan."""
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        plan.app_name,
        "--distpath",
        str(plan.dist_dir),
        "--workpath",
        str(stage_root / "pyinstaller-work"),
        "--specpath",
        str(stage_root),
        "--paths",
        str(stage_root / PACKAGE_NAME),
        "--paths",
        str(plan.toolkit_root),
        "--hidden-import",
        "gl_utils",
        "--collect-all",
        "moderngl",
        "--collect-all",
        "glcontext",
        "--onefile" if plan.onefile else "--onedir",
        "--console" if plan.console else "--windowed",
    ]
    for hidden_import in plan.hidden_imports:
        command.extend(("--hidden-import", hidden_import))
    for source, destination in data_files:
        command.extend(("--add-data", f"{source}{os.pathsep}{destination}"))
    if plan.icon is not None:
        command.extend(("--icon", str(plan.icon)))
    command.append(str(launcher))
    return command


def build_plan(args: argparse.Namespace, toolkit_root: Path) -> tuple[BundlePlan, dict]:
    """Validate CLI arguments and return an executable bundle plan."""
    project_root = resolve_project(toolkit_root, args.project)
    manifest = load_manifest(project_root)
    app_name = sanitize_app_name(args.name or project_root.name)
    dist_dir = Path(args.dist_dir).expanduser() if args.dist_dir else toolkit_root / "dist"
    if not dist_dir.is_absolute():
        dist_dir = toolkit_root / dist_dir
    icon = None
    if args.icon:
        icon = Path(args.icon).expanduser()
        if not icon.is_absolute():
            icon = project_root / icon
        icon = icon.resolve()
        if not icon.is_file():
            raise BundleError(f"Icon file not found: {icon}")

    plan = BundlePlan(
        toolkit_root=toolkit_root,
        project_root=project_root,
        app_name=app_name,
        entry=args.entry,
        dist_dir=dist_dir.resolve(),
        onefile=args.onefile,
        console=args.console,
        include_bitmaps=args.include_bitmaps,
        icon=icon,
        hidden_imports=tuple(args.hidden_import),
    )
    return plan, manifest


def execute_bundle(plan: BundlePlan, manifest: dict, dry_run: bool = False) -> int:
    """Stage and build one project, or print the validated dry-run command."""
    with tempfile.TemporaryDirectory(prefix="pygamekit-bundle-") as temp_name:
        stage_root = Path(temp_name)
        launcher, _ = stage_project(
            plan.project_root, manifest, stage_root, entry=plan.entry
        )
        data_files = collect_data_files(
            plan.toolkit_root,
            plan.project_root,
            manifest,
            include_bitmaps=plan.include_bitmaps,
        )
        command = make_pyinstaller_command(plan, stage_root, launcher, data_files)

        print(f"Project: {plan.project_root}")
        print(f"Target platform: {platform.system()}")
        print(f"Mode: {'one-file' if plan.onefile else 'one-folder'}")
        print(f"Output: {plan.dist_dir}")
        if dry_run:
            print(f"Command: {shlex.join(command)}")
            return 0

        if importlib.util.find_spec("PyInstaller") is None:
            raise BundleError(
                "PyInstaller is not installed. Run: "
                f"{sys.executable} -m pip install -r "
                f"{plan.toolkit_root / 'requirements.txt'}"
            )
        plan.dist_dir.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(command, cwd=plan.toolkit_root, check=False)
        if completed.returncode:
            raise BundleError(
                f"PyInstaller failed with exit code {completed.returncode}"
            )

    print(f"Bundle complete: {plan.dist_dir / plan.app_name}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle a marked PyGameKit project with PyInstaller."
    )
    parser.add_argument(
        "--project",
        help="marked project path; defaults to the only marked project",
    )
    parser.add_argument("--name", help="application/executable name")
    parser.add_argument(
        "--entry", default=DEFAULT_ENTRY, help="project entry point (default: main.py)"
    )
    parser.add_argument("--dist-dir", help="output directory (default: ./dist)")
    parser.add_argument(
        "--onefile", action="store_true", help="create one executable instead of a folder"
    )
    parser.add_argument(
        "--console", action="store_true", help="keep a console window for diagnostics"
    )
    parser.add_argument("--icon", help="optional application icon path")
    parser.add_argument(
        "--include-bitmaps",
        action="store_true",
        help="include editable bitmap JSON sources in the bundle",
    )
    parser.add_argument(
        "--hidden-import",
        action="append",
        default=[],
        help="additional PyInstaller hidden import; repeat as needed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show the build command without invoking PyInstaller",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    toolkit_root = Path(__file__).resolve().parent
    try:
        args = parse_args(argv)
        plan, manifest = build_plan(args, toolkit_root)
        return execute_bundle(plan, manifest, dry_run=args.dry_run)
    except BundleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
