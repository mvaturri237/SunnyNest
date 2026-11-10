# Pause / Resume SunnyNest

These commands stop all 6 scheduled jobs (scraper, the two notification jobs, log rotation, dashboard and backoffice) and keep them off after a restart. Nothing gets deleted. The setup files move into a `sunnynest-paused` folder.

Copy the whole block, paste it into Terminal and press Enter.

## Pause

```bash
mkdir -p ~/Library/LaunchAgents/sunnynest-paused
for j in scraper notify-am notify-pm log-rotate dashboard backoffice; do
  launchctl bootout gui/$(id -u)/com.sunnynest.$j 2>/dev/null
  mv ~/Library/LaunchAgents/com.sunnynest.$j.plist ~/Library/LaunchAgents/sunnynest-paused/ 2>/dev/null
done
launchctl list | grep sunnynest || echo "All SunnyNest jobs stopped"
```

If it worked, the last line says **All SunnyNest jobs stopped**.

## Resume (later)

```bash
for f in ~/Library/LaunchAgents/sunnynest-paused/*.plist; do
  mv "$f" ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$(basename "$f")
done
launchctl list | grep sunnynest
```
