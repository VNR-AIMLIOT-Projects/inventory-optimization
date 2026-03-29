#!/bin/bash
# Oracle Cloud Instance Bootstrap Script
# This script installs Docker and Docker Compose for an Oracle Linux / Ubuntu ARM VM.

set -e

echo "Starting bootstrap configuration for Oracle VM..."

# Detect OS
if grep -q "Oracle Linux" /etc/os-release; then
    echo "Oracle Linux detected."
    # Update packages
    sudo dnf update -y
    # Ensure dnf-utils is installed to manage repositories
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
sudo usermod -aG docker $USER

echo "Bootstrap complete! You may need to log out and log back in for docker group changes to take effect."
echo "Docker is now ready to run 'docker compose up'."
