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



##UX 
Page 1: The Landing & Registration Page
Visual Description:
A clean, minimalist page with a dark theme. The company logo ("QuickList AI") is at the top. Below it is a clear, benefit-driven headline like "Turn Photos into Cash, Faster." The main focus is a simple registration form centered on the page.

     +-------------------------------------------+
     |                                           |
     |                QuickList AI               |
     |   Turn Photos into Cash, Faster.          |
     |                                           |
     |   +-----------------------------------+   |
     |   |        Create Your Account        |   |
     |   |                                   |   |
     |   |  Username: [_____________________]  |   |
     |   |  Email:    [_____________________]  |   |
     |   |  Password: [*********************]  |   |
     |   |                                   |   |
     |   | [  Sign Up for 3-Day Free Trial   ] |   |
     |   +-----------------------------------+   |
     |                                           |
     |     Already have an account? Log In       |
     |                                           |
     +-------------------------------------------+
Key Elements:

Username, Email, and Password input fields.

A primary call-to-action button: "Sign Up for 3-Day Free Trial".

A secondary link for existing users: "Log In".

User Action & System Response:

When the user... fills out the form and clicks "Sign Up".

The system... creates their account, sets their subscription_status to 'trial' with a 3-day trial_end_date, and redirects them to the Login Page with a success message: "Your account has been created! Your 3-day trial has begun."

Page 2: The Login Page
Visual Description:
Even simpler than the registration page. It displays the success message from registration at the top.

     +-------------------------------------------+
     | [✓ Your account has been created! ...]    |
     |                                           |
     |                QuickList AI               |
     |                                           |
     |   +-----------------------------------+   |
     |   |  Email:    [_____________________]  |   |
     |   |  Password: [*********************]  |   |
     |   |                                   |   |
     |   | [            Log In             ] |   |
     |   +-----------------------------------+   |
     +-------------------------------------------+
User Action & System Response:

When the user... enters their credentials and clicks "Log In".

The system... verifies their credentials and redirects them to the main application dashboard.

Page 3: The Main Application Dashboard
Visual Description:
This is the user's workspace. A persistent header shows their status. The main content area is clean and focused on the first action.

     +-------------------------------------------------------------+
     | QuickList AI   | [Trial ends in 3 days]  My Subscription    |
     |                |            Hello, User! [Logout]          |
     +-------------------------------------------------------------+
     |                                                             |
     |   Step 1: Find Your Item                                    |
     |   +-----------------------------------------------------+   |
     |   |                                                     |   |
     |   |  [ Drag & Drop a Photo or Click to Upload ]         |   |
     |   |               [ Take Photo ]                        |   |
     |   +-----------------------------------------------------+   |
     |                                                             |
     |   [                  Find My Item                     ]   |
     |                                                             |
     +-------------------------------------------------------------+
Key Elements:

Header: Shows the brand, trial status, username, and logout link.

Upload Area: A large, clear zone for uploading or taking a photo.

Primary Button: A "Find My Item" button to start the analysis.

User Action & System Response:

When the user... uploads an image and clicks "Find My Item".

The system... hides the upload form and displays the "Loading State". It sends the image to the backend /api/identify-item endpoint.

Page 4: The Loading State (Overlay)
Visual Description:
This is not a new page but an overlay on the Dashboard. The background is dimmed, and a spinner or animation appears with text that manages expectations.

     +-------------------------------------------------------------+
     |                                                             |
     |            /-\                                              |
     |            | |  <-- (Spinner Animation)                     |
     |            \-/                                              |
     |                                                             |
     |       🔎 Analyzing image with Vertex AI...                  |
     |                                                             |
     +-------------------------------------------------------------+
System Response: When the backend API returns a result, this loading overlay disappears, and the "Confirmation Page" content is displayed.

Page 5: The Confirmation Page
Visual Description:
The AI has returned its findings. The user is presented with one or more "product cards" to choose from. Each card is clearly organized with all the data fetched from the database.

     +-------------------------------------------------------------+
     | Header...                                                   |
     +-------------------------------------------------------------+
     |                                                             |
     |   Step 2: Confirm a Match                                   |
     |   We found the following items. Please select a match.      |
     |                                                             |
     |   +-----------------------------------------------------+   |
     |   | Sony WH-1000XM4 Wireless Headphones                 |   |
     |   | Brand: Sony                                         |   |
     |   | Industry-leading noise canceling...                 |   |
     |   |                                                     |   |
     |   | Attributes:                                         |   |
     |   |  • mpn: 19283-B      • color: Black                  |   |
     |   |                                                     |   |
     |   | [ ✅ This is it! ]                                    |   |
     |   +-----------------------------------------------------+   |
     |                                                             |
     |   +-----------------------------------------------------+   |
     |   | Sony WH-CH510 Wireless Headphones                   |   |
     |   | (Another card for a different potential match...)   |   |
     |   +-----------------------------------------------------+   |
     +-------------------------------------------------------------+
Key Elements:

Product Cards: Each contains the name, brand, description, and the new Attributes list.

Confirmation Button: A clear, primary button on each card ("✅ This is it!").

User Action & System Response:

When the user... clicks the "This is it!" button on a card.

The system... stores the selected product's data and displays the final "Listing Generation Page".

Page 6: The Listing Generation Page
Visual Description:
The final step. A form is pre-filled with all the confirmed product data, allowing the user to make final edits before getting their listing content.

     +-------------------------------------------------------------+
     | Header...                                                   |
     +-------------------------------------------------------------+
     |                                                             |
     |   Step 3: Create Your Listing                               |
     |                                                             |
     |   Title: [For Sale: Sony WH-1000XM4 Headphones]             |
     |                                                             |
     |   Description:                                              |
     |   +-----------------------------------------------------+   |
     |   | Industry-leading noise canceling with Dual...       |   |
     |   |                                                     |   |
     |   +-----------------------------------------------------+   |
     |                                                             |
     |   Condition: [Used - Good ▼]  Price: [$ 227.49]             |
     |      (Listing is 65% of retail)                             |
     |                                                             |
     |   [ Generate Copy & Paste Listing ]                         |
     |                                                             |
     +-------------------------------------------------------------+
Key Elements:

Pre-filled Form: Title, Description, and Price are all automatically populated.

Editable Fields: The user can adjust the condition from a dropdown and change the price.

Final Action Button: "Generate Copy & Paste Listing".

User Action & System Response:

When the user... clicks the final button.

The system... could show a success modal with "Copy Title," "Copy Description," and "Download Images" buttons, completing the core workflow.

Page 7: The Subscription Management Page
Visual Description:
A simple, direct page that changes based on the user's subscription status.

(Trial Expired View)

     +-------------------------------------------------------------+
     | Header...                                                   |
     +-------------------------------------------------------------+
     |                                                             |
     |   Manage Your Subscription                                  |
     |                                                             |
     |   [!] Your free trial has expired.                          |
     |   Please subscribe to continue using QuickList AI.          |
     |                                                             |
     |   [  Subscribe for $10/month  ]                             |
     |                                                             |
     +-------------------------------------------------------------+
Key Elements:

Status Message: A clear message explaining their current status (Trial Active, Trial Expired, or Subscribed).

Action Button: The button changes based on context ("Subscribe Now", "Manage Billing & Invoices").

User Action & System Response:

When the user... clicks "Subscribe".

The system... redirects them to the secure, Stripe-hosted checkout page to complete payment.
