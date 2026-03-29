#!/usr/bin/env bash
# scripts/aws/bootstrap_vm.sh
# Bootstraps the EC2 instance with Docker and NVIDIA drivers.

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <EC2_PUBLIC_IP> <AWS_KEY_PAIR.pem>"
    exit 1
fi

EC2_IP=$1
KEY_FILE=$2

echo "Bootstrapping AWS EC2 instance at $EC2_IP..."

ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$EC2_IP << 'EOF'
set -e

echo "Updating system..."
sudo apt-get update && sudo apt-get upgrade -y

echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

echo "Installing NVIDIA drivers..."
sudo apt-get install -y linux-headers-$(uname -r)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID | sed -e 's/\.//g')
wget https://developer.download.nvidia.com/compute/cuda/repos/$distribution/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-drivers nvidia-driver-535 nvidia-utils-535

echo "Installing NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "Setup complete. A reboot is highly recommended."
EOF

echo "Bootstrapping finished successfully."
echo "Please run: ssh -i $KEY_FILE ubuntu@$EC2_IP 'sudo reboot'"
