#!/usr/bin/env python3
"""
Live ISO Builder - Minimal Arch Linux ISO with ZFS support

This script builds a minimal Arch Linux live ISO designed as a boot gateway
for Ansible deployments. It uses zfspin for kernel/ZFS version pinning.

Usage:
    python scripts/build-iso.py [--output-dir DIR] [--work-dir DIR]

Requirements:
    - archiso package
    - zfspin (pip install zfspin)
    - Root privileges
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def log(level: str, msg: str):
    """Simple logging."""
    colors = {
        "INFO": "\033[32m",
        "WARN": "\033[33m",
        "ERROR": "\033[31m",
        "STEP": "\033[34m",
    }
    reset = "\033[0m"
    color = colors.get(level, "")
    print(f"{color}[{level}]{reset} {msg}")


def run_cmd(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a command with logging."""
    log("INFO", f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def load_config(config_path: Path) -> dict:
    """Load configuration from TOML file."""
    if not config_path.exists():
        log("WARN", f"Config file not found: {config_path}, using defaults")
        return {}

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def setup_pinned_kernel_repo(work_dir: Path) -> tuple[str, str]:
    """
    Use zfspin to setup a local repository with pinned kernel/ZFS packages.

    Returns:
        Tuple of (kernel_package_name, zfs_package_name)
    """
    log("STEP", "Setting up pinned kernel/ZFS repository...")

    try:
        from zfspin import PinningConfig
        from zfspin.repository import LocalRepository
        from zfspin.downloader import ArchiveDownloader
        from zfspin.builder import AURBuilder

        # Auto-detect compatible versions with LTS fallback
        config = PinningConfig.auto_detect_with_fallback()
        log("INFO", f"Detected kernel: {config.kernel_version}")
        log("INFO", f"Detected ZFS utils: {config.zfs_utils_version}")

        # Create local repository
        repo_dir = work_dir / "pinned-repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        repo = LocalRepository(repo_dir)

        # Download kernel packages
        downloader = ArchiveDownloader()
        kernel_pkgs = downloader.download_kernel_packages(
            config.kernel_version,
            repo_dir
        )

        # Build zfs-utils from AUR
        builder = AURBuilder()
        zfs_utils_pkg = builder.build_zfs_utils(
            config.zfs_utils_commit,
            repo_dir
        )

        # Add packages to local repo
        repo.add_packages(kernel_pkgs + [zfs_utils_pkg])

        # Determine package names
        kernel_name = "linux-lts" if "lts" in config.kernel_version else "linux"
        zfs_name = f"zfs-{kernel_name}"

        return kernel_name, zfs_name, repo_dir

    except ImportError:
        log("ERROR", "zfspin not installed. Install with: pip install zfspin")
        sys.exit(1)
    except Exception as e:
        log("ERROR", f"Failed to setup pinned repo: {e}")
        sys.exit(1)


def setup_archiso_profile(work_dir: Path, repo_root: Path) -> Path:
    """Setup archiso profile from releng template."""
    log("STEP", "Setting up archiso profile...")

    profile_dir = work_dir / "profile"

    # Copy releng profile as base
    releng_path = Path("/usr/share/archiso/configs/releng")
    if not releng_path.exists():
        log("ERROR", "archiso not installed. Install with: pacman -S archiso")
        sys.exit(1)

    shutil.copytree(releng_path, profile_dir)

    # Copy our minimal packages list
    packages_src = repo_root / "iso" / "packages.x86_64"
    packages_dst = profile_dir / "packages.x86_64"
    shutil.copy(packages_src, packages_dst)

    # Copy airootfs customizations
    airootfs_src = repo_root / "iso" / "airootfs"
    airootfs_dst = profile_dir / "airootfs"

    if airootfs_src.exists():
        for item in airootfs_src.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(airootfs_src)
                dst_path = airootfs_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(item, dst_path)

    return profile_dir


def inject_ssh_keys(profile_dir: Path, config: dict, repo_root: Path):
    """Inject SSH authorized keys into the ISO."""
    log("STEP", "Injecting SSH authorized keys...")

    ssh_config = config.get("ssh", {})
    keys_file = ssh_config.get("authorized_keys_file", "config/ssh-keys")
    keys_path = repo_root / keys_file

    if not keys_path.exists():
        log("WARN", f"SSH keys file not found: {keys_path}")
        log("WARN", "No SSH keys will be injected - you may not be able to SSH in!")
        return

    # Read keys
    with open(keys_path) as f:
        keys = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not keys:
        log("WARN", "SSH keys file is empty")
        return

    # Create authorized_keys in airootfs
    auth_keys_dir = profile_dir / "airootfs" / "root" / ".ssh"
    auth_keys_dir.mkdir(parents=True, exist_ok=True)

    auth_keys_file = auth_keys_dir / "authorized_keys"
    with open(auth_keys_file, "w") as f:
        f.write("\n".join(keys) + "\n")

    auth_keys_file.chmod(0o600)
    auth_keys_dir.chmod(0o700)

    log("INFO", f"Injected {len(keys)} SSH key(s)")


def configure_pacman(profile_dir: Path, pinned_repo_dir: Path | None):
    """Configure pacman.conf with ArchZFS and pinned repos."""
    log("STEP", "Configuring pacman repositories...")

    pacman_conf = profile_dir / "pacman.conf"

    # Read existing config
    with open(pacman_conf) as f:
        content = f.read()

    # Add ArchZFS repository
    archzfs_repo = """
[archzfs]
Server = https://archzfs.com/$repo/$arch
Server = https://mirror.sum7.eu/archlinux/archzfs/$repo/$arch
"""

    # Add pinned repo if available
    pinned_repo = ""
    if pinned_repo_dir:
        pinned_repo = f"""
[pinned]
SigLevel = Optional TrustAll
Server = file://{pinned_repo_dir}
"""

    # Insert before [core]
    if "[core]" in content:
        content = content.replace("[core]", f"{pinned_repo}{archzfs_repo}[core]")

    with open(pacman_conf, "w") as f:
        f.write(content)


def enable_services(profile_dir: Path):
    """Enable required services for live environment."""
    log("STEP", "Enabling live environment services...")

    wants_dir = profile_dir / "airootfs" / "etc" / "systemd" / "system" / "multi-user.target.wants"
    wants_dir.mkdir(parents=True, exist_ok=True)

    services = [
        "sshd.service",
        "NetworkManager.service",
    ]

    for service in services:
        link = wants_dir / service
        target = f"/usr/lib/systemd/system/{service}"
        if not link.exists():
            link.symlink_to(target)


def build_iso(profile_dir: Path, work_dir: Path, output_dir: Path):
    """Run mkarchiso to build the ISO."""
    log("STEP", "Building ISO with mkarchiso...")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mkarchiso",
        "-v",
        "-w", str(work_dir / "work"),
        "-o", str(output_dir),
        str(profile_dir)
    ]

    run_cmd(cmd)

    # Find the generated ISO
    for iso in output_dir.glob("*.iso"):
        log("INFO", f"ISO created: {iso}")
        return iso

    return None


def main():
    parser = argparse.ArgumentParser(description="Build minimal Arch Linux ZFS live ISO")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for ISO")
    parser.add_argument("--work-dir", "-w", help="Work directory (default: temp)")
    parser.add_argument("--config", "-c", default="config/live-iso.toml", help="Config file")
    parser.add_argument("--skip-pinning", action="store_true", help="Skip kernel pinning (use latest)")
    args = parser.parse_args()

    # Check root
    if os.geteuid() != 0:
        log("ERROR", "This script must be run as root")
        sys.exit(1)

    # Setup paths
    repo_root = Path(__file__).parent.parent.resolve()
    output_dir = Path(args.output_dir).resolve()
    config_path = repo_root / args.config

    # Load config
    config = load_config(config_path)

    # Create work directory
    if args.work_dir:
        work_dir = Path(args.work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup_work = False
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="live-iso-"))
        cleanup_work = True

    try:
        log("STEP", f"Work directory: {work_dir}")

        # Setup pinned kernel/ZFS repo
        pinned_repo_dir = None
        if not args.skip_pinning:
            kernel_name, zfs_name, pinned_repo_dir = setup_pinned_kernel_repo(work_dir)

        # Setup archiso profile
        profile_dir = setup_archiso_profile(work_dir, repo_root)

        # Configure pacman
        configure_pacman(profile_dir, pinned_repo_dir)

        # Inject SSH keys
        inject_ssh_keys(profile_dir, config, repo_root)

        # Enable services
        enable_services(profile_dir)

        # Build ISO
        iso_path = build_iso(profile_dir, work_dir, output_dir)

        if iso_path:
            log("STEP", "Build complete!")
            log("INFO", f"ISO: {iso_path}")
            log("INFO", f"Size: {iso_path.stat().st_size / 1024 / 1024:.1f} MB")
        else:
            log("ERROR", "ISO build failed")
            sys.exit(1)

    finally:
        if cleanup_work:
            log("INFO", f"Cleaning up work directory: {work_dir}")
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
