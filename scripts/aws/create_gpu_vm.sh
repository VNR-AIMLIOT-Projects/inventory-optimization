#!/usr/bin/env bash
# scripts/aws/create_gpu_vm.sh
# Creates an AWS EC2 g4dn.xlarge instance for production.

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <ENV_FILE> [AWS_KEY_NAME] [AWS_SECURITY_GROUP_ID]"
    echo "Example: $0 .env.prod my-key-pair sg-0abcd1234"
    exit 1
fi

ENV_FILE=$1
AWS_KEY_NAME=${2:-"inventory-prod-key"}
AWS_SG_ID=${3:-""}

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found."
    exit 1
fi

echo "Deploying AWS EC2 Provisioning..."

# If Security Group isn't provided, create one temporarily
if [ -z "$AWS_SG_ID" ]; then
    echo "No Security Group specified. Creating a new one (inventory-optimization-sg)..."
    AWS_SG_ID=$(aws ec2 create-security-group \
        --group-name inventory-optimization-sg \
        --description "Security group for Inventory Optimization prod" \
        --query 'GroupId' --output text)
    
    # Add rules
    aws ec2 authorize-security-group-ingress --group-id $AWS_SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --group-id $AWS_SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --group-id $AWS_SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --group-id $AWS_SG_ID --protocol tcp --port 3000 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --group-id $AWS_SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0

    echo "Created SG: $AWS_SG_ID"
fi

# Run Instance using Ubuntu 22.04 LTS
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
    --instance-type g4dn.xlarge \
    --key-name "$AWS_KEY_NAME" \
    --security-group-ids "$AWS_SG_ID" \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=inventory-optimization-prod}]' \
    --query 'Instances[0].InstanceId' --output text)

echo "Created EC2 Instance: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "Instance is running at IP: $PUBLIC_IP"
echo "Please add $PUBLIC_IP to your GitHub Secrets as EC2_HOST."
