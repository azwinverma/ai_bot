#!/usr/bin/env bash
# One-shot provisioning for an Oracle Always Free (or any Ubuntu) VM.
# Usage on the VM:  bash setup_vm.sh
set -euo pipefail

REPO="https://github.com/azwinverma/ai_bot.git"
APP_DIR="$HOME/ai_bot"

echo "==> 0/6 Verifying Binance is reachable from this host"
# The gate. Binance geo-blocks api.binance.com from many datacenter IPs; the bot
# uses the public data-only mirror instead. If this is not 200, nothing below
# will work and the region/host has to change — fail now, not after a full build.
code=$(curl -s -o /dev/null -w "%{http_code}" https://data-api.binance.vision/api/v3/ping || true)
if [ "$code" != "200" ]; then
  echo "FATAL: data-api.binance.vision returned HTTP $code (expected 200)."
  echo "This host cannot reach Binance market data. Stop here."
  exit 1
fi
echo "    OK (HTTP 200)"

echo "==> 1/6 System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip git curl

echo "==> 2/6 Swap (only if RAM < 2GB)"
# VM.Standard.E2.1.Micro has 1GB, where `pip install pandas` reliably OOMs.
# The Ampere A1 shapes have plenty and skip this.
mem_mb=$(free -m | awk '/^Mem:/{print $2}')
if [ "$mem_mb" -lt 2000 ] && [ ! -f /swapfile ]; then
  echo "    ${mem_mb}MB RAM detected — adding 2GB swap"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
else
  echo "    ${mem_mb}MB RAM — no swap needed"
fi

echo "==> 3/6 Clone or update repo"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone -q "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> 4/6 Virtualenv + dependencies"
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
# selenium/webdriver/firebase are for the separate TMS broker bot and pull in a
# lot on ARM; the signal engine needs none of them.
./venv/bin/pip install -q python-binance pandas pandas-ta-classic numpy requests python-dotenv anthropic

echo "==> 5/6 Environment file"
if [ ! -f "$APP_DIR/.env" ]; then
  cat > "$APP_DIR/.env" <<'ENVEOF'
# Telegram is the only hard requirement.
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
# Optional: omit to drop the AI insight line from flip alerts.
ANTHROPIC_API_KEY=
# The bot reads only PUBLIC market data, so Binance keys are NOT required.
ENVEOF
  chmod 600 "$APP_DIR/.env"
  echo "    Created $APP_DIR/.env — fill in your Telegram values, then re-run step 6."
else
  echo "    .env already exists — leaving it alone"
fi

echo "==> 6/6 systemd service"
sudo cp "$APP_DIR/deploy/crypto-bot.service" /etc/systemd/system/crypto-bot.service
sudo systemctl daemon-reload
sudo systemctl enable crypto-bot >/dev/null 2>&1
echo
echo "Done. Next:"
echo "  1. nano ~/ai_bot/.env          # fill TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"
echo "  2. sudo systemctl restart crypto-bot"
echo "  3. journalctl -u crypto-bot -f  # watch it run"
