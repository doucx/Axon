#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import tomllib
from packaging.version import parse as parse_version


def get_workspace_root():
    return Path(__file__).parent.parent


def get_pypi_version(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return parse_version(data["info"]["version"])
        elif response.status_code == 404:
            return None
    except Exception as e:
        print(f"Warning: Could not fetch version for {package_name}: {e}")
    return None


def run_cmd(cmd, cwd=None, env=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"--- STDOUT ---\n{result.stdout}")
        print(f"--- STDERR ---\n{result.stderr}")
        return False
    return True


def release_package(pkg_path, pkg_name, local_version):
    print(f"--- Releasing {pkg_name} v{local_version} ---")

    # 0. Clean old artifacts
    dist_dir = pkg_path / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # 1. Build
    # Explicitly set --out-dir to ensure artifacts are in the package's local dist/
    if not run_cmd(["uv", "build", "--out-dir", "dist"], cwd=pkg_path):
        return False

    # 2. Expand wildcards for twine
    # Twine needs a list of actual file paths, only include valid distribution formats
    dist_files = []
    for pattern in ["*.whl", "*.tar.gz"]:
        dist_files.extend([str(f) for f in dist_dir.glob(pattern) if f.is_file()])

    if not dist_files:
        print(f"Error: No build artifacts found in {dist_dir}")
        return False

    # 3. Upload (using twine)
    upload_cmd = ["python3", "-m", "twine", "upload", "--skip-existing"] + dist_files
    if not run_cmd(upload_cmd):
        return False

    # 4. Tag
    tag_name = f"{pkg_name}/v{local_version}"
    # Use --force to allow re-tagging if a previous run failed mid-way
    if not run_cmd(["git", "tag", "-f", tag_name]):
        print(f"Warning: Failed to create tag {tag_name}")

    return True


def main():
    root = get_workspace_root()
    root_toml_path = root / "pyproject.toml"

    with open(root_toml_path, "rb") as f:
        root_toml = tomllib.load(f)

    members_raw = root_toml.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    pkg_dirs = []
    for member in members_raw:
        if member.endswith("/*"):
            base_dir = root / member[:-2]
            if base_dir.exists():
                pkg_dirs.extend([d for d in base_dir.iterdir() if d.is_dir()])
        else:
            pkg_dirs.append(root / member)

    success_count = 0
    fail_count = 0

    for pkg_dir in pkg_dirs:
        toml_path = pkg_dir / "pyproject.toml"
        if not toml_path.exists():
            continue

        with open(toml_path, "rb") as f:
            pkg_toml = tomllib.load(f)

        pkg_name = pkg_toml.get("project", {}).get("name")
        local_ver_str = pkg_toml.get("project", {}).get("version")

        if not pkg_name or not local_ver_str:
            continue

        local_ver = parse_version(local_ver_str)
        remote_ver = get_pypi_version(pkg_name)

        if remote_ver is None or local_ver > remote_ver:
            reason = "New package" if remote_ver is None else f"Update ({remote_ver} -> {local_ver})"
            print(f"Found candidate: {pkg_name} ({reason})")
            if release_package(pkg_dir, pkg_name, local_ver_str):
                success_count += 1
            else:
                fail_count += 1
        else:
            print(f"Skipping {pkg_name}: Up to date (Local: {local_ver}, Remote: {remote_ver})")

    if success_count > 0:
        # Push tags with --force to handle updated tags from retries
        run_cmd(["git", "push", "origin", "--tags", "-f"])

    print(f"\nSummary: {success_count} released, {fail_count} failed.")
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
