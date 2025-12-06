# live-iso

Minimal Arch Linux live ISO with ZFS support - a boot gateway for Ansible deployments.

## Overview

This ISO is intentionally minimal (~15 packages). Its only purpose is to:

1. Boot the target machine
2. Provide network access (NetworkManager)
3. Allow SSH access for Ansible deployment

All actual system configuration is done via [ansible-deploy](https://github.com/MrLutik/ansible-deploy) from your control machine.

## Included Packages

- Base system (base, linux-lts, firmware)
- ZFS support (zfs-linux-lts, zfs-utils)
- Network (NetworkManager, openssh)
- Console (terminus-font with ter-132n)
- Minimal tools (sudo, less, nano, python)

## Building

### Prerequisites

- Arch Linux with `archiso` package
- Python 3.10+
- zfspin (`pip install zfspin`)
- Root privileges

### Build locally

```bash
# Install dependencies
sudo pacman -S archiso python-pip
pip install zfspin

# Add your SSH keys
cp config/ssh-keys.example config/ssh-keys
# Edit config/ssh-keys with your public keys

# Build ISO
sudo python scripts/build-iso.py --output-dir output
```

### Build with Docker

```bash
./docker/build-docker.sh
```

## Configuration

Edit `config/live-iso.toml` for:

- Console font and keymap
- SSH configuration
- Timezone

### SSH Keys

**Important**: Add your SSH public keys to `config/ssh-keys` before building!

```bash
cp config/ssh-keys.example config/ssh-keys
echo "ssh-ed25519 AAAA... user@host" >> config/ssh-keys
```

## Usage

1. Build the ISO
2. Boot target machine from ISO
3. Note the IP address (shown on console)
4. From control machine: `ansible-playbook -i target-ip, playbooks/bootstrap.yml`

## Kernel/ZFS Pinning

The build process uses [zfspin](https://github.com/MrLutik/zfspin) to automatically detect and pin compatible kernel/ZFS versions from archzfs.com.

- Prefers LTS kernel for stability
- Falls back to standard kernel if LTS unavailable
- Ensures kernel and ZFS module are always compatible

## License

MIT License - see [LICENSE](LICENSE)
