# RestroFlow Deployment

## Option 1: Render (recommended)
1. Push this repo to GitHub.
2. In Render, click **New +** -> **Web Service**.
3. Connect your GitHub repo and select this project.
4. Render will detect `render.yaml` automatically.
5. Deploy.

### Manual settings (if not using `render.yaml`)
- Runtime: `Python`
- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`
- Environment variable: `HOST=0.0.0.0`
- Persistent disk mount path: `/var/data`
- Environment variable: `DB_PATH=/var/data/restroflow.sqlite3`

## Option 2: Railway
1. Push this repo to GitHub.
2. In Railway, click **New Project** -> **Deploy from GitHub repo**.
3. Select this repo.
4. Railway will run the app using `Procfile` (`python server.py`).

## Important note about SQLite
- Your app uses `restroflow.sqlite3`.
- On most cloud platforms, local filesystem changes may be ephemeral.
- That means new data (orders/feedback/queries) may reset on restart/redeploy.
- For production persistence, use a managed database (e.g. PostgreSQL) or attach persistent disk support.
