# Scheduled Email Notification Feature — Implementation Plan

## Overview

Add a **decoupled notification service** that runs twice daily (8:00 AM and 8:00 PM) to check for new unnotified listings in the **local database** (no external API calls) and send an email digest to `maorvaturri@gmail.com`. The service is designed with a **channel adapter pattern** to support future notification channels (WhatsApp, Slack, etc.) and includes a **hard anti-spam block** limiting to 2 notifications per day maximum.

---

## Current State

| Component | File | Status |
|-----------|------|--------|
| Email sender (SMTP/Gmail) | `src/notifier.py` | ✅ Exists — will be refactored into channel adapter |
| Background scheduler (APScheduler) | `src/scheduler.py` | ✅ Exists — needs cron job added |
| `Listing.notified` flag | `src/models.py:115` | ✅ Exists — already a boolean column |
| `upsert_listing()` sets `notified=False` | `src/database.py:260` | ✅ Exists — new listings start unnotified |
| Query for unnotified listings | `src/database.py` | ❌ Missing |
| Mark listings as notified | `src/database.py` | ❌ Missing |
| Notification log (anti-spam) | `src/models.py` | ❌ Missing |
| Channel adapter pattern | `src/notifier.py` | ❌ Missing |
| Cron-based notification schedule | `src/scheduler.py` | ❌ Missing |

---

## Architecture

### High-Level Flow

```
APScheduler (cron: 8:00 AM / 8:00 PM, Asia/Jerusalem)
  │
  ▼
┌─────────────────────────────────────────────┐
│  NotificationService.run()                  │
│                                             │
│  1. Anti-spam check:                        │
│     Query NotificationLog for today's count │
│     If count >= MAX_DAILY (2) → ABORT       │
│                                             │
│  2. Query local DB:                         │
│     SELECT * FROM listings                  │
│     WHERE notified = False                  │
│     AND is_active = True                    │
│     (NO external API calls)                 │
│                                             │
│  3. If 0 results → skip, no email           │
│                                             │
│  4. Dispatch to channel adapters:           │
│     ┌──────────────┐  ┌──────────────┐      │
│     │ EmailChannel  │  │ (WhatsApp)   │      │
│     │ (implemented) │  │ (future)     │      │
│     └──────────────┘  └──────────────┘      │
│                                             │
│  5. On success:                             │
│     - Mark listings as notified = True      │
│     - Log to NotificationLog table          │
│                                             │
│  6. On failure:                             │
│     - Log error                             │
│     - Listings remain unnotified            │
│     - NO NotificationLog entry (doesn't     │
│       count against daily limit)            │
└─────────────────────────────────────────────┘
```

### Channel Adapter Pattern

```
                    ┌───────────────────────┐
                    │  BaseNotificationChannel  │  (ABC)
                    │                       │
                    │  + send(listings, config) -> bool  │
                    │  + channel_name: str   │
                    └───────────┬───────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
    ┌───────────▼──┐  ┌────────▼───────┐  ┌────▼──────────┐
    │ EmailChannel │  │ WhatsAppChannel│  │ SlackChannel  │
    │ (v1 — now)   │  │ (future)       │  │ (future)      │
    └──────────────┘  └────────────────┘  └───────────────┘
```

Each channel:
- Implements `send(listings, config) -> bool`
- Has its own config section in `config.yaml`
- Is registered in the `NotificationService` via a list of enabled channels
- Can be toggled on/off independently

### Anti-Spam Protection

```
┌──────────────────────────────────────────────┐
│  NotificationLog (new DB table)              │
│                                              │
│  id          INTEGER  PK                     │
│  channel     TEXT     "email" / "whatsapp"   │
│  sent_at     DATETIME                        │
│  listing_count INTEGER                       │
│  recipient   TEXT                             │
│  success     BOOLEAN                         │
└──────────────────────────────────────────────┘

Hard block logic (in NotificationService.run()):
  today_count = SELECT COUNT(*) FROM notification_log
                WHERE date(sent_at) = date('now')
                AND success = True
  
  if today_count >= MAX_DAILY_NOTIFICATIONS (2):
      logger.warning("Daily notification limit reached (%d/%d). Skipping.")
      return  # HARD BLOCK — no email sent
```

**Why this is safe:**
- The limit is checked **before** any send attempt
- Only **successful** sends count against the limit
- The constant `MAX_DAILY_NOTIFICATIONS = 2` is defined at module level, not in config (can't be accidentally overridden)
- Even if the scheduler fires more than twice (e.g., manual trigger), the hard block prevents spam

---

## Detailed Changes

### 1. `src/models.py` — Add `NotificationLog` model

New ORM model to track every notification sent:

```python
class NotificationLog(Base):
    __tablename__ = "notification_log"
    
    id: int           # PK auto-increment
    channel: str      # "email", "whatsapp", etc.
    sent_at: datetime # When the notification was sent
    listing_count: int # How many listings were included
    recipient: str    # Who received it
    success: bool     # Whether it was delivered successfully
```

### 2. `src/database.py` — Add notification query functions

**`get_unnotified_listings() -> list[Listing]`**
- Query: `SELECT * FROM listings WHERE notified = False AND is_active = True ORDER BY first_seen DESC`
- Returns ORM objects (no API calls, pure DB read)

**`mark_listings_notified(listing_ids: list[int]) -> None`**
- Bulk update: `UPDATE listings SET notified = True WHERE id IN (...)`
- Single transaction

**`log_notification(channel, listing_count, recipient, success) -> None`**
- Insert a row into `notification_log`

**`get_today_notification_count() -> int`**
- Query: `SELECT COUNT(*) FROM notification_log WHERE date(sent_at) = date('now') AND success = True`
- Used by the anti-spam hard block

### 3. `src/notifier.py` — Refactor into channel-based architecture

**New structure:**

```python
# --- Abstract base ---
class BaseNotificationChannel(ABC):
    """Base class for all notification channels."""
    
    @property
    @abstractmethod
    def channel_name(self) -> str: ...
    
    @abstractmethod
    def send(self, listings: list[dict], config: dict) -> bool: ...


# --- Email channel (existing logic, refactored) ---
class EmailChannel(BaseNotificationChannel):
    channel_name = "email"
    
    def send(self, listings, config) -> bool:
        # Existing SMTP logic from send_notification()
        # Updated subject: "X new listing added"
        # Updated body: includes dashboard link
        ...


# --- Notification service (orchestrator) ---
MAX_DAILY_NOTIFICATIONS = 2  # Hard-coded, not configurable

class NotificationService:
    def __init__(self, channels: list[BaseNotificationChannel], config: dict):
        self.channels = channels
        self.config = config
    
    def run(self) -> dict:
        # 1. Anti-spam check
        # 2. Query unnotified listings from DB
        # 3. Dispatch to each enabled channel
        # 4. Mark as notified on success
        # 5. Log to NotificationLog
        ...
```

**Email format changes:**
- **Subject**: `"X new listing added"` (where X = count of new listings)
- **Body**: Existing HTML table of listing details + new "View Dashboard →" button linking to `dashboard_url` from config

### 4. `src/scheduler.py` — Add cron notification job

- Add a second job `_NOTIFICATION_JOB_ID = "notification_check"` 
- Register with `CronTrigger(hour='8,20', minute=0, timezone='Asia/Jerusalem')`
- The job calls `NotificationService.run()`
- Runs alongside the existing interval-based scrape job (they are independent)

### 5. `config.yaml` — Updated configuration

```yaml
# Email notifications
email:
  enabled: true
  smtp_server: smtp.gmail.com
  smtp_port: 587
  sender_email: ""          # Set via env var or here
  sender_password: ""       # Use Gmail app-specific password
  recipient_email: "maorvaturri@gmail.com"
  dashboard_url: "http://localhost:8501"

# Notification schedule (cron-based, independent of scraping)
notification_schedule:
  hours: [8, 20]            # 8:00 AM and 8:00 PM
  timezone: "Asia/Jerusalem"
  
# Future channel configs would go here:
# whatsapp:
#   enabled: false
#   api_key: ""
#   phone_number: ""
```

### 6. `requirements.txt` — No changes needed

APScheduler already supports `CronTrigger`. No new dependencies for the email channel.

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `config.yaml` | Modify | Set `recipient_email`, add `dashboard_url`, add `notification_schedule` |
| `src/models.py` | Modify | Add `NotificationLog` model for anti-spam tracking |
| `src/database.py` | Modify | Add `get_unnotified_listings()`, `mark_listings_notified()`, `log_notification()`, `get_today_notification_count()` |
| `src/notifier.py` | Refactor | Extract `BaseNotificationChannel` ABC, create `EmailChannel`, create `NotificationService` with anti-spam hard block |
| `src/scheduler.py` | Modify | Add cron-based notification job alongside existing scrape job |

---

## Key Design Decisions

### 1. DB-Only, No API Calls
The notification job **only reads from the local SQLite database**. It queries `listings` where `notified = False`. No Zillow/Craigslist API calls are made. The scraper populates the DB separately on its own schedule.

### 2. Anti-Spam Hard Block
- `MAX_DAILY_NOTIFICATIONS = 2` is a **module-level constant** (not configurable via YAML to prevent accidental override)
- Checked via `NotificationLog` table query before any send attempt
- Only successful sends count against the limit
- Even manual triggers respect the limit

### 3. Channel Adapter Pattern (Future-Proof)
- `BaseNotificationChannel` ABC defines the contract: `send(listings, config) -> bool`
- `EmailChannel` implements it now using existing SMTP logic
- Future channels (WhatsApp, Slack, SMS) implement the same interface
- `NotificationService` iterates over registered channels and dispatches to each
- Each channel has its own config section and can be enabled/disabled independently

### 4. Decoupled from Scraping
The notification schedule (cron at 8:00/20:00) is completely independent from the scrape schedule (interval-based). This means:
- Scrapes can run at any frequency without triggering notifications
- Notifications aggregate all unnotified listings since the last successful send
- If a scrape fails, previously discovered listings are still notified

### 5. Backward Compatible
The existing inline notification in `ScraperOrchestrator._notify_new_listings()` can remain as-is or be removed. The new `NotificationService` is the primary notification path. The old code path would be redundant but harmless (it would try to send for listings that the scheduled job will also pick up, but the `notified` flag prevents double-sending).

---

## Testing Considerations

- Unit test `get_unnotified_listings()` returns only `notified=False, is_active=True` listings
- Unit test `get_today_notification_count()` correctly counts today's successful sends
- Unit test the anti-spam hard block: after 2 successful sends, `NotificationService.run()` should abort
- Unit test `EmailChannel.send()` with mocked SMTP
- Integration test: insert unnotified listings → run service → verify they're marked notified
