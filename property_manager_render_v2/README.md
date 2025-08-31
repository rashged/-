# Property Manager (Flask)

## Run locally
```bash
pip install -r requirements.txt
python property_manager_improved_app.py
```

Then open http://127.0.0.1:5000

Default login:
- Email: admin@example.com
- Password: admin123

## Deploy on Render
1. Push this repo to GitHub.
2. Create a new **Web Service** on Render.
3. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `bash start.sh`
4. Done! Your app will be live.
