# 🏠 Sunnyvale Rental Finder

An automated rental listing aggregator for **Sunnyvale, CA**. The app scrapes listings from Zillow and Craigslist, stores them in a local SQLite database, and presents them through an interactive Streamlit dashboard with filtering, map view, charts, and email notifications.

---

## ✨ Features

- **Automated scraping** from Zillow and Craigslist every 6 hours (configurable)
- **Interactive Streamlit dashboard** with sidebar filters
- **Map view** with color-coded markers (by source and price range)
- **Listing cards** with price, bedrooms, size (sqft + m²), neighborhood, school district, pet-friendly badge, and images
- **Charts**: price distribution, price trends over time, listings by category, and value analysis
- **Email notifications** for new listings matching your filters
- **Manual sync trigger** — run a scrape on demand from the dashboard
- **Configurable filters**: price range, bedrooms, bathrooms, property type, pet-friendly, parking, and more

---

## 📸 Screenshots

> _Screenshots coming soon — run the app and explore!_

---

## 📋 Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- A modern web browser (for the Streamlit dashboard)

---

## 🚀 Quick Start

1. **Clone or navigate to the project directory**

   ```bash
   cd zillow
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   ```

   On Windows:
   ```bash
   python -m venv .venv && .venv\Scripts\activate
   ```

   > **Note (macOS):** macOS does not provide a `python` command — always use `python3`.
   > After activating the venv, both `python` and `python3` will work.

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browser**

   ```bash
   playwright install chromium
   ```

5. **(Optional) Configure email notifications**

   Edit `config.yaml` and fill in the `email` section (see [Email Setup](#-email-setup) below).

6. **Run the app**

   ```bash
   streamlit run app.py
   ```

7. **Open your browser** at [http://localhost:8501](http://localhost:8501)

---

## ⚙️ Configuration

All settings live in [`config.yaml`](config.yaml). The file has five sections:

### `search`
Defines the target location for scraping.

| Key | Description | Default |
|-----|-------------|---------|
| `city` | Target city | `Sunnyvale` |
| `state` | Target state | `CA` |
| `zip_codes` | List of ZIP codes to search | `94085, 94086, 94087, 94089` |

### `filters`
Default filter values applied on startup.

| Key | Description | Default |
|-----|-------------|---------|
| `min_price` | Minimum monthly rent ($) | `5000` |
| `max_price` | Maximum monthly rent ($) | `6500` |
| `min_bedrooms` | Minimum bedrooms | `3` |
| `max_bedrooms` | Maximum bedrooms | `4` |
| `property_types` | Allowed property types | `house` |

### `schedule`
Controls the automatic scraping interval.

| Key | Description | Default |
|-----|-------------|---------|
| `interval_hours` | Hours between automatic scrapes | `6` |

### `email`
Email notification settings (disabled by default).

| Key | Description | Default |
|-----|-------------|---------|
| `enabled` | Enable/disable email notifications | `false` |
| `smtp_server` | SMTP server address | `smtp.gmail.com` |
| `smtp_port` | SMTP port | `587` |
| `sender_email` | Sender email address | `""` |
| `sender_password` | Sender email password (app-specific) | `""` |
| `recipient_email` | Recipient email address | `""` |

### `scraper`
Controls scraper behavior to avoid rate-limiting.

| Key | Description | Default |
|-----|-------------|---------|
| `request_delay_min` | Minimum delay between requests (seconds) | `3` |
| `request_delay_max` | Maximum delay between requests (seconds) | `8` |
| `max_pages` | Maximum pages to scrape per source | `5` |

---

## 📧 Email Setup

To receive email notifications for new matching listings:

1. **Use a Gmail account** (recommended).
2. **Enable 2-Factor Authentication** on your Google account.
3. **Generate an App-Specific Password**:
   - Go to [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and your device
   - Copy the generated 16-character password
4. **Update `config.yaml`**:
   ```yaml
   email:
     enabled: true
     smtp_server: smtp.gmail.com
     smtp_port: 587
     sender_email: "your-email@gmail.com"
     sender_password: "xxxx xxxx xxxx xxxx"  # App-specific password
     recipient_email: "your-email@gmail.com"
   ```

---

## 📁 Project Structure

```
zillow/
├── README.md                        # This file
├── config.yaml                      # User configuration (filters, email, schedule)
├── requirements.txt                 # Python dependencies
├── app.py                           # Streamlit dashboard entry point
├── com.sunnynest.dashboard.plist    # macOS Launch Agent definition
├── src/
│   ├── __init__.py
│   ├── models.py                    # SQLAlchemy Listing data model
│   ├── database.py                  # Database connection, queries, upsert logic
│   ├── geocoder.py                  # Address → lat/lng conversion (geopy/Nominatim)
│   ├── school_districts.py          # School district lookup by ZIP code
│   ├── orchestrator.py              # Coordinates scrapers, enrichment, storage
│   ├── scheduler.py                 # APScheduler background job management
│   ├── notifier.py                  # Email notification service
│   ├── utils.py                     # Shared utilities (config loader, unit conversion, logging)
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py                  # Abstract base scraper class
│       ├── zillow_scraper.py        # Zillow scraper (Playwright-based)
│       └── craigslist_scraper.py    # Craigslist scraper (httpx + BeautifulSoup)
├── scripts/
│   ├── start-dashboard.sh           # Starts Streamlit (used by Launch Agent)
│   ├── install-service.sh           # Installs the macOS Launch Agent
│   └── uninstall-service.sh         # Removes the macOS Launch Agent
├── data/
│   ├── .gitkeep
│   └── listings.db                  # SQLite database (auto-created at runtime)
├── logs/                            # Service log files (gitignored)
└── plans/
    └── architecture.md              # Architecture and design document
```

---

## 🔄 How It Works

The application follows a **scrape → enrich → store → display** pipeline:

1. **Scraping** — The `ScraperOrchestrator` runs the Zillow and Craigslist scrapers on a configurable schedule (default: every 6 hours). Zillow uses Playwright for browser automation (JS-heavy site); Craigslist uses httpx + BeautifulSoup for lightweight HTML parsing.

2. **Enrichment** — Each raw listing is enriched with:
   - **Geocoding**: Address is converted to latitude/longitude via geopy (Nominatim) for map placement.
   - **School district**: ZIP code is mapped to the corresponding Sunnyvale school district.
   - **Normalization**: Fields like price, bedrooms, and square footage are parsed into consistent formats.

3. **Storage** — Listings are upserted into a local SQLite database (`data/listings.db`) using SQLAlchemy. Duplicate detection is based on the external listing ID and source. Listings no longer found in scrapes are marked inactive.

4. **Display** — The Streamlit dashboard reads from the database and presents:
   - Sidebar filters (price, bedrooms, property type, etc.)
   - Summary metrics (total listings, median price, etc.)
   - Interactive map with color-coded markers
   - Listing cards with all details
   - Analytical charts (price distribution, trends, value analysis)

5. **Notifications** — When new listings matching the configured filters are found, an email notification is sent (if enabled).

---

## 🔄 Running as a Persistent Service (macOS)

The dashboard can be configured as a **macOS Launch Agent** so it starts automatically on login and restarts if it crashes — no more finding the dashboard down every morning.

### Install the service

```bash
bash scripts/install-service.sh
```

This will:
- Create the `logs/` directory for service output
- Copy the Launch Agent plist to `~/Library/LaunchAgents/`
- Load and start the service immediately
- The dashboard will now start automatically on every login

### Check service status

```bash
# Check if the agent is loaded and get its PID
launchctl list | grep sunnynest
```

The output columns are: `PID`, `exit status`, `label`. A numeric PID means the process is running. A `-` means it's loaded but not currently running. A non-zero exit status indicates a crash.

### View logs

```bash
# Follow stderr log (Streamlit output)
tail -f logs/dashboard-stderr.log

# Follow stdout log
tail -f logs/dashboard-stdout.log
```

### Stop / Start the service manually

```bash
# Stop (unload) the service
launchctl unload ~/Library/LaunchAgents/com.sunnynest.dashboard.plist

# Start (load) the service
launchctl load ~/Library/LaunchAgents/com.sunnynest.dashboard.plist
```

### Uninstall the service

```bash
bash scripts/uninstall-service.sh
```

This stops the service and removes the plist from `~/Library/LaunchAgents/`. Log files in `logs/` are preserved.

---

## 🛠️ Troubleshooting

### Playwright not installed
```
Error: Executable doesn't exist at ...
```
**Fix**: Run `playwright install chromium` to download the browser binary.

### Zillow blocking requests
Zillow aggressively blocks automated access. If scraping fails:
- Increase `request_delay_min` and `request_delay_max` in `config.yaml`
- Reduce `max_pages`
- The app will still work with Craigslist data and any previously scraped Zillow listings

### No listings appearing
- Click the **"🔄 Sync Now"** button in the dashboard to trigger a manual scrape
- Check the terminal output for scraping errors
- Verify your `config.yaml` filters aren't too restrictive

### Database errors
If the database becomes corrupted, delete `data/listings.db` and restart the app. A fresh database will be created automatically.

### Email notifications not working
- Ensure `email.enabled` is set to `true` in `config.yaml`
- Verify you're using a Gmail **App-Specific Password** (not your regular password)
- Check that 2-Factor Authentication is enabled on your Google account
- Look for SMTP errors in the terminal output

### Port already in use
```
Address already in use
```
**Fix**: Run on a different port: `streamlit run app.py --server.port 8502`

---

## 📄 License

This project is for personal use.
