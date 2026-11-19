"""Build a cross-platform MCPB using an explicit, credential-free file allowlist."""

import json
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build_bundle(project: Path, output_dir: Path) -> Path:
    """Package only runtime code and metadata, not the developer's environment."""
    manifest_path = project / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    if manifest["version"] != version:
        raise ValueError("manifest.json version must match pyproject.toml before packaging.")
    if manifest["name"] != "radia-jama":
        raise ValueError("Unexpected desktop extension name.")
    files = [
        manifest_path,
        project / "pyproject.toml",
        project / "uv.lock",
        project / "README.md",
        project / "desktop" / "server.py",
        *sorted((project / "mcp_radia").rglob("*.py")),
    ]
    for path in files:
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(project.resolve())
        ):
            raise ValueError(f"Missing or unsafe bundle input: {path.name}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"radia-jama-{version}.mcpb"
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(project).as_posix())
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    print(build_bundle(root, root / "dist"))
