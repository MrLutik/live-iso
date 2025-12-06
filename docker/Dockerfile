# Dockerfile for building the live ISO
# Uses Arch Linux as base with archiso tools

FROM archlinux:latest

# Install build dependencies
RUN pacman -Syu --noconfirm \
    archiso \
    python \
    python-pip \
    git \
    && pacman -Scc --noconfirm

# Install zfspin
RUN pip install --break-system-packages zfspin

# Import ArchZFS GPG key
RUN pacman-key --recv-keys --keyserver keyserver.ubuntu.com DDF7DB817396A49B2A2723F7403BD972F75D9D76 \
    && pacman-key --lsign-key DDF7DB817396A49B2A2723F7403BD972F75D9D76

WORKDIR /live-iso

COPY . .

ENTRYPOINT ["python", "scripts/build-iso.py"]
CMD ["--output-dir", "/output"]
