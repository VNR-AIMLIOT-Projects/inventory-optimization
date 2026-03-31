#!/bin/bash
# DigitalOcean Droplet Bootstrap Script
# Provision a standard 2GB Swap buffer for kernel stability and install Docker Engine

set -e

echo "Starting bootstrap configuration for DigitalOcean Droplet..."

# 1. CONFIGURE SWAP FILE (Safety Buffer)
if [ -f /swapfile ] || grep -q "swap" /etc/fstab; then
    echo "Swap space already exists."
else
    echo "Allocating 2GB Swap Space..."
    
    # Try fallocate first (faster), fallback to dd if unsupported on the filesystem
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    
    # Secure and format
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Persist across reboots
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    
    # Standard server swappiness
    sudo sysctl vm.swappiness=10
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
    
    echo "Swap space successfully configured!"
    free -m
fi

# 2. INSTALL DOCKER ENGINE (Ubuntu 24.04/22.04)
echo "Installing Docker..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to Docker group to allow running without sudo
echo "Adding user ${USER} to docker group..."
sudo usermod -aG docker $USER || true

echo "Bootstrap complete! Swap is active, Docker is ready."
echo "You may need to log out and log back in for docker group changes to take effect."
