# QuickList AI - Setup and Deployment Guide

This guide will walk you through deploying the QuickList AI application using Docker and Docker Compose.

## Step 1: Prerequisites

1.  A server (VPS or home server) with a domain name pointed to its IP address.
2.  Docker and Docker Compose installed on the server.
3.  A Google Cloud account with billing enabled.
4.  A Stripe account.

## Step 2: Configuration

### a. Clone or Create Project Files
Create the project structure as laid out in the documentation. Copy all the provided files into it.

### b. Set up Google Cloud
1.  **Enable APIs:** In the Google Cloud Console, enable the **Vertex AI API**, **Cloud Storage API**, and **Cloud Vision API**.
2.  **Service Account:** Create a service account. Grant it the roles **Vertex AI User** and **Storage Object Admin**.
3.  **JSON Key:** Create and download a JSON key for this service account. Rename it to `google-credentials.json` and place it in the root of the project directory.
4.  **Cloud Storage:** Create a new Cloud Storage bucket with a globally unique name.

### c. Create Your `.env` File
1.  In the project root, create a file named `.env`.
2.  Copy the contents of the `.env.example` file into it.
3.  Fill out every variable as described in the `.env.example` template. Pay close attention to where to find each Stripe and Google Cloud value.

## Step 3: Build the AI Search Index (One-Time Task)

This step populates the Vertex AI Matching Engine with your product data.

1.  **Update `create_index.py`:** Open the `create_index.py` file and change the `PROJECT_ID` and `BUCKET_NAME` variables at the top to match your Google Cloud project and bucket.
2.  **Authenticate Locally:** In your local terminal, authenticate the gcloud CLI:
    ```bash
    gcloud auth application-default login
    ```
3.  **Run the script:**
    ```bash
    pip install -r requirements.txt
    python create_index.py
    ```
4.  **IMPORTANT:** The script will output three IDs (Index ID, Endpoint ID, and Deployed Index ID). **You must copy these values into your `.env` file.**

## Step 4: Deploy the Application on Your Server

1.  **Transfer Files:** Copy your entire project directory (including your `.env` and `google-credentials.json` files) to your server.
2.  **SSH into your server** and navigate to the project directory.
3.  **Initialize Certificate Files (Once):** Run these commands to create dummy files so Nginx can start.
    ```bash
    sudo mkdir -p data/certbot/conf
    curl -L https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "data/certbot/conf/options-ssl-nginx.conf"
    curl -L https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "data/certbot/conf/ssl-dhparams.pem"
    ```
4.  **Start Nginx and the Web App:**
    ```bash
    docker-compose up -d web nginx
    ```
5.  **Request Production SSL Certificate:** Replace `your_domain.com` and your email.
    ```bash
    docker-compose run --rm --entrypoint "\
      certbot certonly --webroot -w /var/www/certbot \
      --email your_email@example.com \
      -d your_domain.com \
      --agree-tos \
      --no-eff-email \
      --force-renewal" certbot
    ```
6.  **Restart Nginx to Apply Certificate:**
    ```bash
    docker-compose restart nginx
    ```

Your application is now live at `https://your_domain.com`.

## Step 5: Configure Stripe Webhook

1.  In your Stripe Dashboard, go to **Developers > Webhooks**.
2.  Click **+ Add endpoint**.
3.  Set the Endpoint URL to `https://your_domain.com/stripe-webhook`.
4.  Select the events to listen for:
    *   `checkout.session.completed`
    *   `customer.subscription.deleted`
5.  Click **Add endpoint**. The webhook signing secret should already be in your `.env` file.
