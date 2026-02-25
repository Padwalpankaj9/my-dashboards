# My Dashboards

Bespoke personal dashboards. Static HTML + Vercel.

## Live Apps

| App | Description | Link |
|-----|-------------|------|
| Subscription Tracker | Spending trends, student plan alerts | [Open](https://my-dashboards-vert.vercel.app/) |
| OpenClaw Architecture | VPS internals, network, skills, cron, secrets | [Open](https://my-dashboards-vert.vercel.app/openclaw.html) |
| Mac Helicopter View | Full AI/CLI/MCP setup visibility snapshot | [Open](https://my-dashboards-vert.vercel.app/helicopter.html) |

## Adding a New App

1. Create a new `.html` file in this repo
2. `git push` (Vercel auto-deploys)
3. Access at `https://my-dashboards-vert.vercel.app/filename.html`
4. Add the link to the table above

## Mac Helicopter View (Visibility Only)

### Files
- `helicopter.html`: Dashboard UI
- `data/snapshot.json`: Latest generated snapshot data
- `data/history.json`: Rolling history points for trend chart
- `scripts_generate_helicopter_snapshot.py`: Snapshot generator

### Generate Snapshot Manually

```bash
cd ~/Documents/my-dashboards
python3 scripts_generate_helicopter_snapshot.py
```

### Cron Job (Every 6 Hours)

```bash
0 */6 * * * cd /Users/apple/Documents/my-dashboards && /opt/homebrew/bin/python3 scripts_generate_helicopter_snapshot.py >/tmp/helicopter-snapshot.log 2>&1
```

### Deploy Flow
1. Run snapshot generator.
2. Commit updated `data/snapshot.json` and dashboard changes.
3. Push to GitHub.
4. Vercel auto-deploys and serves fresh visibility dashboard.
