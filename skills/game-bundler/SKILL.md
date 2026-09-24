---
name: game-bundler
description: Bundle, package, export, or ship a marked PyGameKit project as a native desktop release using the repository's bundle_game.py workflow. Use for macOS apps, Windows executables, Linux bundles, one-folder or one-file releases, and packaging diagnostics.
---

# PyGameKit Game Bundler

Use the toolkit-root `bundle_game.py` command for packaging. Do not create a
parallel PyInstaller script, copy `gl_utils.py` into the project, or manually
rearrange the shared shaders. The exporter stages the game and preserves the
documented project/toolkit path layout inside the frozen application.

## Complete Bundle Workflow

When the user directly asks to bundle, package, export, or ship a game, carry
the workflow through dependency setup, validation, build, and artifact report:

1. Work from the toolkit root containing `bundle_game.py` and
   `requirements.txt`.
2. Resolve the requested project directory and require its
   `.pygamekit-project` marker. If no project is named, use the only marked
   project. If multiple marked projects exist, stop and ask which one to use.
3. Install the complete shared environment once per session:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

   If sandbox or network restrictions block installation, request approval and
   retry the same command. Do not continue with missing dependencies.
4. Refresh the selected project's generated marker inventory with the
   repository bootstrap workflow before packaging.
5. Validate the exact bundle configuration first:

   ```bash
   python3 bundle_game.py --project "<project-root>" --dry-run
   ```

6. Build the recommended one-folder release unless the user explicitly asks
   for a single-file release:

   ```bash
   python3 bundle_game.py --project "<project-root>" --name "<app-name>"
   ```

   Add `--onefile` only when requested or after the one-folder build has been
   validated. Use `--console` when diagnosing a launch failure. Pass project
   requirements that use dynamic imports through repeatable
   `--hidden-import MODULE` arguments.
7. Require a successful exporter exit status and inspect `dist/` for the
   expected artifact. Do not report success based only on the dry run.
8. When the environment permits launching GUI applications, perform a brief
   smoke launch and check for an immediate crash. Request any required GUI
   approval. Do not leave the game process running after verification.
9. Report the artifact path, bundle mode, host target, whether it was smoke
   launched, and exactly what the user must ship. For one-folder releases, the
   whole generated directory must be shipped; for one-file releases, ship the
   generated executable or app artifact.

## Platform Boundary

PyInstaller produces a native build for the host operating system. Build on
Windows for a Windows `.exe`, macOS for a macOS application, and Linux for a
Linux executable. Never claim that a build for another operating system was
produced. If the requested target differs from the host, explain the boundary
and provide the exact command to run on that target instead of fabricating an
artifact.

## Scope and Safety

An explicit packaging request authorizes dependency installation, marker
refresh, exporter execution, and creation or replacement of the matching
artifact under `dist/`. It does not authorize gameplay, asset, engine, or
project-source changes. Diagnose packaging failures first; request expanded
authority before changing source code to resolve one.
