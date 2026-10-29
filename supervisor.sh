#!/bin/bash
while true; do
  python3 /root/fflikes-bot/tg_like_bot.py >> /root/fflikes-bot/tg_bot.log 2>&1
  echo "[$(date)] bot crashed, restarting in 5s..." >> /root/fflikes-bot/tg_bot.log
  sleep 5
done
