# opendecks.ca

## Setup Instructions

1. **Initialize Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory. Without these, the application will still function smoothly but will silently skip network notifications.
   ```env
   # Notifications & APIs
   GMAIL_SENDER_EMAIL=dj.antivaxx@gmail.com
   GMAIL_APP_PASSWORD=your_16_char_google_app_password
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   
   # Security (Auto-generated if left blank)
   SECRET_KEY=your_secure_flask_encryption_key
   ```

3. **Run Locally**:
   ```bash
   python src/app.py
   ```
   *The database (`artifacts/database.db`) and user uploads (`artifacts/uploads/`) will be generated automatically on first boot. Navigate to `http://127.0.0.1:5001`.*
