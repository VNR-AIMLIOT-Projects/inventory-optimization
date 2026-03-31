#!/bin/bash
# Oracle Cloud Instance Bootstrap Script (Micro Tier Optimized)
# This script configures a massive Swap file for 1GB RAM constraints,
# then installs Docker and Docker Compose for an Oracle Linux / Ubuntu VM.

set -e

echo "Starting bootstrap configuration for Oracle Micro VM..."

# 1. CONFIGURE MASSIVE SWAP FILE (Crucial for 1GB RAM survival)
if [ -f /swapfile ] || grep -q "swap" /etc/fstab; then
    echo "Swap space already exists."
else
    echo "Allocating 4GB Swap Space... (This prevents PyTorch from crashing the server)"
    
    # Try fallocate first (faster), fallback to dd if unsupported on the filesystem
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    
    # Secure and format
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Persist across reboots
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    
    # Adjust swappiness to aggressively use swap instead of crashing the kernel
    sudo sysctl vm.swappiness=60
    echo 'vm.swappiness=60' | sudo tee -a /etc/sysctl.conf
    
    echo "Swap space successfully configured! Current memory status:"
    free -m
fi

# 2. INSTALL DOCKER ENGINE
echo "Detecting OS for Docker installation..."

if grep -q "Oracle Linux" /etc/os-release; then
    echo "Oracle Linux detected."
    # Update packages
    sudo dnf update -y
    sudo dnf install -y dnf-utils
    
    # Add Docker repository for Oracle Linux
    sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
    
    # Install Docker
    echo "Installing Docker..."
    sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

elif grep -q "Ubuntu" /etc/os-release; then
    echo "Ubuntu detected."
    # Update packages
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
    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "Unsupported OS for this bootstrap script. Please install Docker manually."
    exit 1
fi

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to Docker group to allow running without sudo
echo "Adding user ${USER} to docker group..."
sudo usermod -aG docker $USER || true

echo "Bootstrap complete! Swap is active, Docker is ready."
echo "You may need to log out and log back in for docker group changes to take effect."
