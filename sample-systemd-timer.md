# Optional systemd timer for desktop notifications (Linux)
#
# Cron on headless systems can't always reach your desktop notification bus.
# A systemd **user** timer avoids that problem.
#
# 1. Save as ~/.config/systemd/user/food-tracker.service
#    (adjust WorkingDirectory and python path to your setup)

[Unit]
Description=Emergency food tracker alert check

[Service]
Type=oneshot
WorkingDirectory=/path/to/emergency-food-tracker
ExecStart=/usr/bin/python3 tracker.py check

# 2. Save as ~/.config/systemd/user/food-tracker.timer

[Unit]
Description=Run food tracker check daily at 08:00

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target

# 3. Enable it:
#   systemctl --user daemon-reload
#   systemctl --user enable --now food-tracker.timer
