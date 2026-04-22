# Production Deployment (DigitalOcean via Student Pack)

This guide provides instructions for deploying the Inventory Optimization platform to a **DigitalOcean Droplet**, utilizing the $200 free credit you receive from the GitHub Student Developer Pack.

This architecture runs an **Ubuntu 24.04** Server with **4GB of RAM** and **2 CPUs**, which is more than enough to comfortably power our full PyTorch and React stack.

## 1. Claim your Credits

1. Ensure your university email is added to your GitHub account.
2. Go to the [GitHub Student Developer Pack](https://education.github.com/pack) and claim your benefits.
3. Find the **DigitalOcean** offer and generate your unique link to claim your $200 credit.
4. Create your DigitalOcean account using that link. You will likely need to add a payment method to verify identity, but you will not be charged as your credit dictates your balance.

## 2. Provision the Droplet

1. In the DigitalOcean Control Panel, click green **Create** button in the top right -> **Droplets**.
2. **Region**: Choose the closest region to you (e.g. Bangalore, NYC, London).
3. **Image**: Choose **Ubuntu 24.04 (LTS) x64**.
4. **Size**: Choose **Basic** plan.
   - For CPU options, select **Regular**.
   - Select the **$24.00/month** droplet (4 GB RAM / 2 CPUs / 80 GB SSD). _(Note: This will use up your $200 credit in 8.3 months. If you want it to last 16 months, choose the $12/month 2 GB RAM droplet)._
5. **Authentication Method**: 
   - Click **SSH Key**. 
   - Click **New SSH Key** and paste your public key if you have one, or create one.
   - *Alternatively*, choose **Password** and create a highly secure root password.
6. **Finalize**: Name the droplet `inventory-prod-vm` and click **Create Droplet**.

## 3. Configure GitHub Secrets

Once your droplet boots, DO will give you an IPv4 address. We will configure GitHub Actions (`.github/workflows/deploy-do.yml`) to automatically deploy the application simply by pushing to the `prod` branch.

In your GitHub repository, go to **Settings > Secrets and variables > Actions**, and add the following four secrets:

1. `DO_HOST`: The IPv4 address of your Droplet.
2. `DO_USERNAME`: This is `root` by default on all DO Droplets.
3. `DO_SSH_KEY`: The **private key** corresponding to the SSH key you selected during Droplet creation. *(If you selected Password auth instead of SSH keys in DigitalOcean, you will need to SSH into your server locally and generate an SSH Keypair, adding the public key to `~/.ssh/authorized_keys` and pasting the private key into this GitHub Secret).*
4. `PROD_ENV_FILE`: The contents of your production environment variables.

### Example `PROD_ENV_FILE` configuration:
```env
POSTGRES_USER=inventory_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=inventory_db

RABBITMQ_DEFAULT_USER=rabbit_admin
RABBITMQ_DEFAULT_PASS=your_secure_password

# This URL must map to your Droplet IP address so the React frontend knows where to request data.
BACKEND_PUBLIC_URL=http://YOUR_DROPLET_IP:8000
```

## 4. Deploy

Once your VM is running and your GitHub Secrets are populated:

1. Push your code to the `prod` branch:
   ```bash
   git checkout prod
   git merge main  # Ensure prod has the latest main code!
   git push origin prod
   ```
2. Navigate to the **Actions** tab in your GitHub repository.
3. Watch the `Deploy to DigitalOcean` pipeline execute! 

*Note: Since you are given the `root` user by default on DigitalOcean, there is no need to configure security groups or blocked ports; Traffic to port 8000 (Backend) and 3000 (Frontend) is allowed immediately.*
