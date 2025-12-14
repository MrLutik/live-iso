# Dockerfile for building the live ISO
# Uses Arch Linux as base with archiso tools

FROM archlinux:latest

# Install build dependencies
RUN pacman -Syu --noconfirm \
    archiso \
    python \
    python-pip \
    git \
    curl \
    sudo \
    base-devel \
    && pacman -Scc --noconfirm

# Install zfspin from pacman package
RUN curl -LO https://github.com/MrLutik/zfspin/releases/download/v0.0.1/zfspin-0.0.1-1-any.pkg.tar.zst \
    && pacman -U --noconfirm zfspin-0.0.1-1-any.pkg.tar.zst \
    && rm zfspin-0.0.1-1-any.pkg.tar.zst

# Initialize pacman-key and import ArchZFS GPG key
RUN pacman-key --init \
    && pacman-key --recv-keys --keyserver keyserver.ubuntu.com DDF7DB817396A49B2A2723F7403BD972F75D9D76 \
    && pacman-key --lsign-key DDF7DB817396A49B2A2723F7403BD972F75D9D76

WORKDIR /live-iso

COPY . .

ENTRYPOINT ["python", "scripts/build-iso.py"]
CMD ["--output-dir", "/output"]
