# Beginner's Guide: Deploying DonjonDocs to Production

This step-by-step guide will walk you through deploying your DonjonDocs application for free. We will use **Supabase** for a secure PostgreSQL database and **Render** to host the Python (FastAPI/NiceGUI) application. Both offer generous and permanent free tiers.

I have already added `asyncpg` to your `requirements.txt` file, which allows your application to talk securely and asynchronously to PostgreSQL!

---

## Step 1: Set up Supabase (Your PostgreSQL Database)

Supabase gives you a full PostgreSQL database for free. Since you want to interact with Postgres directly (via SQLAlchemy/Alembic) and not the Supabase API, we only need the connection string.

1. Go to [Supabase](https://supabase.com/) and click **Start your project**.
2. Sign in (usually with GitHub) and create a **New Project**.
   - Choose a secure Database Password (save this somewhere safe, you will need it later).
   - Select the region closest to where you plan to host your app (e.g., US East).
   - Choose the **Free** pricing plan.
3. Wait a few minutes for the database to provision.
4. Once your project is ready, go to **Project Settings** (the gear icon on the left sidebar).
5. Click on **Database** under the Configuration section.
6. Scroll down to **Connection string** and select the **URI** tab. 
   - Make sure **Use connection pooling** is checked (this is crucial for serverless/cloud environments).
   - The connection string will look something like this:
     `postgresql://postgres.yourprojectid:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres`
   - **IMPORTANT:** Replace `[YOUR-PASSWORD]` with the password you created in step 2.
   - **IMPORTANT:** Change `postgresql://` at the very beginning to `postgresql+asyncpg://` so your Python app knows to use the async driver.

Your final connection string should look like:
`postgresql+asyncpg://postgres.yourprojectid:supersecretpassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require` (The `?sslmode=require` ensures the connection is encrypted).

---

## Step 2: Push your Code to GitHub

Hosting platforms like Render pull your code directly from GitHub to build and deploy it.

1. Go to [GitHub](https://github.com/) and create a new **Private** repository (e.g., `donjondocs`).
2. Open a terminal in your project directory and run:
   ```bash
   git init
   git add .
   git commit -m "Ready for deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/donjondocs.git
   git push -u origin main
   ```
*(Note: Be absolutely certain your `.env` file is listed in `.gitignore` and is NOT pushed to GitHub. Never commit secrets!)*

---

## Step 3: Deploy the Application on Render

Render is a fantastic platform for beginners and offers a permanent free tier for web services. 

1. Go to [Render](https://render.com/) and sign up using your GitHub account.
2. In the Render Dashboard, click **New +** and select **Web Service**.
3. Select **Build and deploy from a Git repository** and connect the `donjondocs` repository you just created.
4. Fill out the deployment details:
   - **Name:** donjondocs (or anything you like)
   - **Region:** Choose the same region you selected for Supabase (e.g., US East).
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `alembic upgrade head && python main.py`
     *(Runs your database migrations first, then starts the web server. `main.py` reads Render's `PORT` env var and binds to `0.0.0.0` automatically — no extra flags needed. NiceGUI starts uvicorn internally; do not run `uvicorn main:app` directly, that bypasses NiceGUI's startup hook and the app will fail to boot.)*
   - **Instance Type:** Select **Free** ($0/month).

### Step 4: Configure Secure Environment Variables
Before clicking "Create Web Service", scroll down to the **Environment Variables** section. You need to tell your app how to connect to Supabase and set up security keys. Add the following variables:

1. **`DATABASE_URL`**
   - **Value:** Paste your modified Supabase connection string from Step 1.
2. **`SECRET_KEY`**
   - **Value:** Generate a secure random string and paste it here. (You can generate one by running `python -c "import secrets; print(secrets.token_urlsafe(64))"` in your terminal).
3. **`STORAGE_SECRET`**
   - **Value:** Generate a **second, independent** random string the same way and paste it here. This is used for NiceGUI session storage and must differ from `SECRET_KEY` so a leak of one does not compromise the other. The app will refuse to boot without this value.
4. **`ALLOWED_HOSTS`**
   - **Value:** Your Render service hostname (and any custom domain), comma-separated — e.g. `donjondocs-abcd.onrender.com` or `donjondocs-abcd.onrender.com,donjondocs.example.com`. You'll see the exact `*.onrender.com` URL after the first deploy; come back and set this then. Without it, every request gets a 400 from the trusted-host middleware.
5. **`DEBUG`**
   - **Value:** `false` (Turns off verbose error messages in production to prevent leaking sensitive info).
6. **`HSTS_ENABLED`**
   - **Value:** `true` (Forces browsers to only connect over HTTPS, significantly boosting security).

Click **Create Web Service**. 

---

## Step 5: Verification

1. Render will now start building your application. This can take a few minutes. You can watch the deployment logs on the screen.
2. Once you see "Your service is live 🎉", click the URL at the top left of the Render dashboard (e.g., `https://donjondocs-abcd.onrender.com`).
3. Your app should now be live! The database migrations (`alembic upgrade head`) ran automatically during startup, meaning your Supabase Postgres database has all the correct tables.

> [!TIP]
> **Free Tier Caveats**
> On Render's free tier, your application will "go to sleep" if it doesn't receive any traffic for 15 minutes. When the next person visits the site, it will take about 30-50 seconds to wake up. This is completely normal for free tiers. Supabase's free tier database will pause if not used for 7 days, so just make sure to visit your site at least once a week!

> [!IMPORTANT]
> **Security Checklist**
> - ✅ You are using Postgres natively via `asyncpg`, bypassing the Supabase public API entirely.
> - ✅ `DEBUG=false` prevents stack traces from showing to end users.
> - ✅ `HSTS_ENABLED=true` forces strict HTTPS encryption.
> - ✅ Your database connection is encrypted via SSL/TLS (`pooler.supabase.com`).
> - ✅ Your `.env` secrets are safely stored in Render, not in your code repository.
