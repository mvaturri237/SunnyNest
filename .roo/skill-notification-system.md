# Skill: Notification System Design

## Purpose
Guide the design, implementation, and review of notification systems covering email, SMS, WhatsApp, push notifications, and in-app alerts.

## When to Use
- Designing a notification feature from scratch
- Reviewing notification code for reliability and deliverability
- Choosing notification channels and providers
- Implementing user notification preferences

## Architecture

### Event-Driven Pattern
Notifications should be triggered by events, not embedded in business logic:

1. Business logic emits an event (e.g., "new_listing_ingested")
2. Notification service listens for events
3. Notification service checks user preferences (which channels, which criteria)
4. Notification service formats and sends via appropriate channel
5. Delivery status is tracked and logged

### Core Components
- Event Emitter: publishes events when something notification-worthy happens
- Notification Router: matches events to user preferences and selects channels
- Channel Adapters: one per delivery method (email, WhatsApp, SMS, push)
- Template Engine: renders notification content per channel
- Delivery Tracker: logs send attempts, delivery status, failures
- Preference Store: user settings for what/when/how to notify

### Data Model
- notification_preferences: user_id, channel, enabled, filters (price range, location, beds)
- notification_log: id, user_id, channel, event_type, status (sent/delivered/failed/read), sent_at
- notification_templates: channel, event_type, subject, body_template

## Channel Guide

### Email
- Provider options: SendGrid, AWS SES, Resend, Postmark
- Use HTML templates with inline CSS (email clients strip external CSS)
- Include plain-text fallback
- Add unsubscribe link (legally required: CAN-SPAM, GDPR)
- Rate limit: batch digest emails (don't send 50 individual emails)
- Track: open rate, click rate, bounce rate, unsubscribe rate

### WhatsApp (Business API)
- Provider options: Twilio WhatsApp, Meta Cloud API, MessageBird
- Requires pre-approved message templates (Meta reviews them)
- Template variables for dynamic content (listing address, price, link)
- 24-hour session window: can only send free-form messages within 24h of user's last message
- Outside 24h: must use approved templates only
- Opt-in required: user must explicitly consent to WhatsApp notifications
- Cost: per-message pricing (varies by country)

### SMS
- Provider options: Twilio, Vonage, AWS SNS
- Keep under 160 characters (or it splits into multiple messages = higher cost)
- Include opt-out instructions ("Reply STOP to unsubscribe")
- Cost: per-message pricing

### Push Notifications (Browser/Mobile)
- Web: use Service Workers + Push API
- Mobile: Firebase Cloud Messaging (FCM) for Android, APNs for iOS
- Keep title under 50 chars, body under 100 chars
- Include deep link to the relevant listing
- Don't over-notify: users will disable permissions

### In-App Notifications
- Notification bell icon with unread count badge
- Notification dropdown/panel with recent items
- Mark as read on click
- "Mark all as read" action
- Persist in database (not just real-time)

## Notification Triggers for SunnyNest

| Event | Description | Suggested Channels |
|-------|-------------|-------------------|
| new_listing_match | New listing matches saved search criteria | Email, WhatsApp, Push |
| price_drop | Price decreased on a favorited listing | Email, WhatsApp, Push |
| listing_removed | A favorited listing was removed/rented | Email, In-App |
| sync_complete | Scheduled sync finished with new results | In-App only |
| sync_failed | A source failed to sync | In-App (admin only) |

## User Preferences UI

### Settings Screen Should Include
- Channel toggles: Email (on/off), WhatsApp (on/off), Push (on/off)
- Frequency: Instant, Hourly Digest, Daily Digest
- Quiet hours: Don't notify between 10pm - 8am
- Filter criteria: Only notify for listings matching (price range, beds, location)
- Test button: "Send me a test notification"

### Preference Storage
- Store per-user, per-channel preferences
- Default: email ON (instant), WhatsApp OFF, push OFF
- Respect user timezone for quiet hours and digests

## Digest vs Instant

| Mode | When to Use | Implementation |
|------|-------------|---------------|
| Instant | High-value alerts (price drop on favorite) | Send immediately on event |
| Hourly Digest | Moderate volume (new listings in saved search) | Cron job aggregates events, sends batch |
| Daily Digest | High volume (many new listings) | Cron job at user's preferred time |

### Digest Email Structure
- Subject: "SunnyNest: 5 new rentals in Sunnyvale, CA"
- Body: summary cards with thumbnail, price, beds/baths, link
- Footer: manage preferences link, unsubscribe link

## Reliability & Error Handling

### Retry Strategy
- Attempt 1: immediate
- Attempt 2: after 5 minutes
- Attempt 3: after 30 minutes
- Attempt 4: after 2 hours
- After 4 failures: mark as failed, log error, don't retry

### Failure Handling
- Email bounce: mark email as invalid, notify user in-app to update email
- WhatsApp undelivered: fall back to email
- Push failed: fall back to email
- All channels failed: log and surface in admin dashboard

### Idempotency
- Generate a unique notification_id per event+user combination
- Check if notification_id was already sent before sending
- Prevents duplicate notifications on retry or system restart

## Security & Privacy

- Never include full listing details in SMS (character limit + privacy)
- WhatsApp templates must not contain sensitive user data
- Email: use DKIM, SPF, DMARC to avoid spam folder
- Store notification preferences encrypted at rest
- Provide data export (GDPR: user can request all notification history)
- Provide data deletion (GDPR: user can delete notification history)

## Testing Checklist
- [ ] Test each channel independently (email, WhatsApp, SMS, push)
- [ ] Test with invalid recipient (bad email, wrong phone number)
- [ ] Test retry logic (simulate provider failure)
- [ ] Test digest aggregation (multiple events in one digest)
- [ ] Test quiet hours (notification queued, not sent)
- [ ] Test unsubscribe flow (user opts out, notifications stop)
- [ ] Test duplicate prevention (same event doesn't send twice)
- [ ] Load test: simulate 1000 notifications in 1 minute
