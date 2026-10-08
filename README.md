# opendecks.ca

## Setup Instructions

1. **Initialize Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory.
   ```env
   # Required in production (Vercel). Locally, SQLite + disk uploads are used if these are unset.
   SECRET_KEY=your_secure_flask_encryption_key
   DATABASE_URL=postgres://...  
   BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...
   ADMIN_USERS=antivaxx
   # Optional. Canonical origin for links and the sitemap. Defaults to https://opendecks.ca
   # SITE_URL=https://opendecks.ca
   # Optional. Discord channel webhook. 
   # DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```

3. **Run Locally**:
   ```bash
   python src/app.py
   ```
   *The database (`artifacts/database.db`) and user uploads (`artifacts/uploads/`) will be generated automatically on first boot. Navigate to `http://127.0.0.1:5001`.*
