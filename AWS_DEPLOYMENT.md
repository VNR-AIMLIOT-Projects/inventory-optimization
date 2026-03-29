# AWS Deployment Guide (prod branch)

This guide details how to deploy the entire `inventory-optimization` stack on a single AWS GPU instance (`g4dn.xlarge`), specifically meant for the `prod` branch.
The deployment is automated using a CI/CD pipeline via GitHub Actions.

## 1. Prepare Local Environment

1. Ensure you are on the `prod` branch.
2. Copy `.env.prod.example` to `.env.prod` locally for reference (this will be securely loaded into AWS).
3. Ensure you have the [AWS CLI](https://aws.amazon.com/cli/) installed and configured with your credentials.

```bash
aws configure
```

## 2. Provision AWS Infrastructure

### A. AWS EC2 Instance (g4dn.xlarge)

The `g4dn.xlarge` instance provides 1 NVIDIA T4 GPU, 4 vCPUs, and 16GB of RAM—ideal for our backend RL worker and the rest of the stack.

You can use the helper script or configure it via the AWS Console:

```bash
# Example script assuming you've defined your VPC and Security Group
# ./scripts/aws/create_gpu_vm.sh
aws ec2 run-instances \
    --image-id resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
    --instance-type g4dn.xlarge \
    --key-name your-aws-keypair \
    --security-group-ids sg-xxxxxxxx \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=inventory-optimization-prod}]'
```

### B. Security Groups (Firewall)

Create a Security Group allowing the following inbound traffic:
- **SSH (Port 22)**: From your IP (and GitHub Actions IPs or a proxy if required).
- **HTTP (Port 80)** / **HTTPS (Port 443)**: For public web access.
- **Frontend (Port 3000)**: Optional, if bypassing Nginx for direct access during testing.
- **Backend API (Port 8000)**: Optional, for direct API access.

*Keep Postgres (5432) and RabbitMQ (5672) strictly closed off from the internet.*

## 3. Install Docker + NVIDIA Stack on EC2

Once the VM is running, SSH into it to install Docker, Docker Compose, and the NVIDIA drivers.

```bash
# Helper script or manual commands
./scripts/aws/bootstrap_vm.sh
# Followed by a reboot
ssh -i "your-aws-keypair.pem" ubuntu@<EC2_PUBLIC_IP> 'sudo reboot'
```

After rebooting, verify that the NVIDIA GPU is recognized:
```bash
ssh -i "your-aws-keypair.pem" ubuntu@<EC2_PUBLIC_IP> 'nvidia-smi'
```

## 4. Setup GitHub Actions CI/CD Pipeline

We use GitHub Actions to automate deployments whenever a push is made to the `prod` branch.

### Configure GitHub Secrets

Go to your repository settings -> **Secrets and variables** -> **Actions** -> **New repository secret** and add the following:

- `EC2_HOST`: The Public IP or Domain of the EC2 instance.
- `EC2_USERNAME`: Usually `ubuntu`.
- `EC2_SSH_KEY`: The private `.pem` key contents you generated in AWS to access the EC2.
- `PROD_ENV_FILE`: The complete contents of your `.env.prod` file.

### How the Pipeline Works

1. On `git push` to `prod`, GitHub Actions triggers.
2. It SSHs into the EC2 instance using the provided `EC2_SSH_KEY`.
3. It creates or updates the `.env.prod` file on the server.
4. It checks out the latest repository code directly on the server.
5. It runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` to automatically rebuild and restart the updated containers without downtime (for stateless containers).

## 5. Validate the Deployment

Once the GitHub Action completes successfully, verify the system is running:

**From your browser:**
- Frontend: `http://<EC2_PUBLIC_IP>:3000` (or your domain)
- API Docs: `http://<EC2_PUBLIC_IP>:8000/docs`

**From the EC2 Server:**
```bash
docker ps
docker logs -f inventory-optimization-rl-worker-1
```

Confirm the GPU is available inside the RL worker container:
```bash
docker exec -it inventory-optimization-rl-worker-1 python -c "import torch; print('CUDA:', torch.cuda.is_available(), 'DEVICE:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

## 6. AWS Cost Management

- An On-Demand `g4dn.xlarge` instance costs roughly ~$380/month if left running 24/7.
- **Stop the VM** when you are not actively testing or using the application:
  ```bash
  aws ec2 stop-instances --instance-ids i-0xxxxxxxxxxxxxxxxx
  ```
- **Start the VM** when needed:
  ```bash
  aws ec2 start-instances --instance-ids i-0xxxxxxxxxxxxxxxxx
  ```
- Set up **AWS Budget Alerts** in the Billing Dashboard (e.g., at $50, $100 limits).
