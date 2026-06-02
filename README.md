# FordTracker

A personal GPS tracker and vehicle dashboard for Ford vehicles with FordPass Connect. Automatically records every drive as a GPS route, displays trip history on an interactive map, and shows live vehicle stats — all from your browser.

![Dashboard showing fuel gauge, tire pressures, and map](https://placehold.co/900x400/1a1d27/0066cc?text=FordTracker+Dashboard)

---

## Features

- **GPS Trip Recording** — automatically detects when you start driving and records a GPS breadcrumb trail. Trips are saved to a local SQLite database.
- **Interactive Map** — view any trip as a colored polyline on an OpenStreetMap map. Browse all trips at once or jump to a specific one.
- **Live Dashboard** — fuel level with history sparkline, estimated range, oil life, odometer, battery voltage, tire pressures (all four corners), lock status, and alarm status.
- **Trip History** — sortable table of all trips with date, start/end time, duration, and distance. Click any row to jump to its route on the map.
- **Stats** — trips and total distance for the past 7 days, 30 days, and all time.
- **Background Daemon** — runs as a systemd user service so trips are captured even when the browser is closed.
- **Demo Mode** — try the full UI with fake data, no credentials needed.

---

## Requirements

- Python 3.11+
- A Ford vehicle with **FordPass Connect** active (2020+ model year)
- Your FordPass account credentials (email + password)
- Your vehicle VIN

---

## Installation

**1. Clone the repo**

```bash
git clone git@github.com:M0uidev/FordTracker.git
cd FordTracker
```

**2. Create the virtual environment and install dependencies**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**3. Configure credentials**

```bash
cp .env.example .env
```

Edit `.env` and fill in your details:

```env
FORDPASS_EMAIL=your@email.com
FORDPASS_PASSWORD=yourpassword
FORDPASS_VIN=your_vin_here
```

> Your VIN is on the driver-side dashboard (visible through the windshield), on your registration card, or in the FordPass app under **Account → Your Vehicles**.

**4. Install the `fordtracker` command globally** (optional)

```bash
make install
```

This symlinks `fordtracker` into `~/.local/bin` so you can run it from anywhere.

---

## Running

### Normal mode

```bash
fordtracker
# or without make install:
./fordtracker
```

Opens `http://localhost:8421` in your browser automatically.

### Demo mode (no credentials needed)

```bash
fordtracker --demo
```

Loads the full UI with 8 pre-seeded fake trips around Austin, TX and simulated vehicle data. Great for exploring the interface before connecting your truck.

### Options

```
--demo          Run with fake demo data (no credentials needed)
--port PORT     Port to listen on (default: 8421)
--no-browser    Don't auto-open the browser
-h, --help      Show help
```

---

## Running as a background daemon

Install as a systemd user service so FordTracker starts automatically on login and records trips even when the browser is closed:

```bash
cp fordtracker.service ~/.config/systemd/user/
systemctl --user enable --now fordtracker
```

Check status:

```bash
systemctl --user status fordtracker
journalctl --user -u fordtracker -f
```

Stop or disable:

```bash
systemctl --user stop fordtracker
systemctl --user disable fordtracker
```

---

## How it works

FordTracker connects to your vehicle through the **unofficial FordPass API** (the same endpoints used by the FordPass mobile app). Every 3 minutes it fetches your vehicle's status, stores a snapshot, and runs a trip detection state machine:

- **Trip starts** when the vehicle moves more than 50 metres from its last recorded position.
- **Trip continues** as long as new movement is detected within 10 minutes.
- **Trip ends** after 10 minutes of no movement — the route is finalized and saved.

All data is stored locally in a SQLite database (`fordtracker.db`). No data is sent anywhere else.

---

## Project structure

```
FordTracker/
├── tracker/
│   ├── config.py       — environment variable loading
│   ├── fordapi.py      — FordPass API wrapper → typed dataclasses
│   ├── trips.py        — Haversine distance + trip state machine
│   ├── daemon.py       — asyncio background poll loop
│   ├── database.py     — SQLite queries
│   ├── demo.py         — fake data for demo mode
│   └── main.py         — FastAPI server + REST API
├── frontend/
│   ├── index.html      — single-page dashboard (Dashboard / Map / Trips)
│   ├── app.js          — vanilla JS frontend
│   └── style.css       — dark theme
├── fordtracker         — executable launcher script
├── fordtracker.service — systemd user unit
├── Makefile
└── requirements.txt
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `FORDPASS_EMAIL` | — | FordPass account email |
| `FORDPASS_PASSWORD` | — | FordPass account password |
| `FORDPASS_VIN` | — | Vehicle Identification Number |
| `POLL_INTERVAL_SECONDS` | `180` | How often to poll the API (seconds) |
| `TRIP_TIMEOUT_MINUTES` | `10` | Idle time before a trip is closed |
| `MOVEMENT_THRESHOLD_METERS` | `50` | Minimum movement to record a new GPS point |
| `DB_PATH` | `fordtracker.db` | Path to the SQLite database |
| `DEMO_MODE` | `false` | Set to `true` to use fake data |

---

## Disclaimer

This project uses the unofficial, reverse-engineered FordPass API. It is not affiliated with or endorsed by Ford Motor Company. Use at your own risk — misuse may violate Ford's Terms of Service.
