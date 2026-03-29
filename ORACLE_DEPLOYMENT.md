# Zero-Cost Production Deployment (Oracle Cloud)

This guide provides instructions for deploying the Inventory Optimization platform to a **100% Free** server using the Oracle Cloud Infrastructure (OCI) "Always Free" tier. 

Because we are deploying across the free tier, we are utilizing Oracle's ARM Ampere A1 Compute instances (up to 4 ARM CPUs and 24 GB of RAM), which provides incredible performance at absolutely zero cost.

## 1. Provision the Oracle Cloud Instance

1. Create a free account at [Oracle Cloud](https://www.oracle.com/cloud/free/).
2. In the OCI Console, navigate to **Compute > Instances** and click **Create instance**.
3. **Name**: `inventory-prod-vm` (or similar).
4. **Image and Shape**: 
   - Click **Edit**.
   - Select **Oracle Linux** (or **Ubuntu**).
   - Change shape: Select **Virtual machine**, then **Ampere (ARM)**, and choose the `VM.Standard.A1.Flex` shape.
   - Configure up to **4 OCPUs** and **24 GB Memory** (this is fully covered by the Always Free tier).
5. **Networking**: Ensure you assign a public IPv4 address.
6. **Add SSH Keys**: Save the Private Key to your computer.
7. Click **Create**.

## 2. Configure VCN Ingress Rules (Security Group)

Unlike AWS, Oracle by default blocks almost all ports. You must explicitly open them in your Virtual Cloud Network (VCN):

1. Once the instance is running, click on its attached **Subnet**.
2. Click on the **Security List** associated with the subnet.
3. Add **Ingress Rules** for the following ports:
   - **8000** (Backend / FastAPI)
   - **3000** (Frontend / UI)
   - **15672** (RabbitMQ Management - *Optional*)

*(Note: Depending on your OS image, you may also need to open these ports in iptables/firewalld directly on the machine via SSH).*

## 3. Configure GitHub Secrets

This repository uses GitHub Actions (`.github/workflows/deploy-oracle.yml`) to automatically deploy code directly to your Oracle VM whenever changes are pushed to the `prod` branch.

In your GitHub repository, go to **Settings > Secrets and variables > Actions**, and add the following four secrets:

1. `ORACLE_HOST`: The Public IP address of your Oracle instance.
2. `ORACLE_USERNAME`: The default SSH user (e.g., `ubuntu` for Ubuntu images, or `opc` for Oracle Linux).
3. `ORACLE_SSH_KEY`: The **entire contents** of the private key file (`.key` or `.pem`) you downloaded when creating the instance. Include the `-----BEGIN...` and `-----END...` lines.
4. `PROD_ENV_FILE`: The contents of your production environment variables.

### Example `PROD_ENV_FILE` configuration:
```env
POSTGRES_USER=inventory_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=inventory_db

RABBITMQ_DEFAULT_USER=rabbit_admin
RABBITMQ_DEFAULT_PASS=your_secure_password

# The public IP of your Oracle VM so the frontend knows where to fetch data
BACKEND_PUBLIC_URL=http://YOUR_ORACLE_PUBLIC_IP:8000
```

## 4. Deploy

Once your VM is running and your GitHub Secrets are set up:

1. Push your code to the `prod` branch:
   ```bash
   git checkout prod
   git merge origin/main
   git push origin prod
   ```
2. Navigate to the **Actions** tab in your GitHub repository.
3. Watch the `Deploy to Oracle Cloud` pipeline execute!

Because we rely on standard CPU operations and ARM64-compatible python libraries, compiling the PyTorch CPU wheels might take an extra minute during the very first Docker build, but subsequent deploys will be fully cached.
