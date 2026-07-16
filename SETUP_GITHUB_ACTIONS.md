# Run the crypto signal bot 24/7 with GitHub Actions (free)

Your laptop no longer needs to stay on. GitHub runs the hourly check in the cloud.
The bot's last SAR side is stored in **`crypto_state.json`, which the workflow commits
back to the repo** whenever it changes — so each hourly run continues exactly where the
previous one left off, with no external database required.

## How it works
- `.github/workflows/crypto-signal.yml` runs every hour (`cron: "5 * * * *"`).
- Each run does one `python crypto_tracker.py --once --interval 1h` and exits.
- If SAR flips (evaluated on the last *closed* candle), you get a Telegram alert
  **and** the new state is committed back to `crypto_state.json` (commits only happen
  on a flip, so the repo stays quiet otherwise).

## One-time setup

### 1. Push this project to GitHub
```bash
cd /Users/aswiniverma/Documents/PersonalProject/ai_bot
git init
git add .
git commit -m "Add hourly GitHub Actions signal runner"
# create an EMPTY private repo on github.com first, then:
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```
> The `.gitignore` already excludes `.env` and `service_account.json`, so your
> secrets are NOT uploaded. They go in as GitHub Secrets instead (next step).

### 2. Add repository secrets
On GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Add each of these (values come from your local `.env`):

| Secret name | Value |
|---|---|
| `BINANCE_API_KEY` | your Binance API key |
| `BINANCE_SECRET_KEY` | your Binance secret |
| `TELEGRAM_BOT_TOKEN` | your Telegram bot token |
| `TELEGRAM_CHAT_ID` | your Telegram chat id |
| `ANTHROPIC_API_KEY` | (optional) for the AI insight line |

> State is kept in `crypto_state.json` in the repo, so **no Firebase / service
> account is needed** for the hourly signal — those are only used by the local
> dashboard (`app.py`).

Optional model override: under the **Variables** tab add `ANTHROPIC_MODEL`
(e.g. `claude-sonnet-5`). If unset, the code default is used.

### 3. Test it now
GitHub → **Actions** tab → **Crypto SAR Signal** → **Run workflow**.
Watch the logs; you should see the price table and indicator readout. A Telegram
message is only sent when SAR actually flips (or if there's an error).

## Good to know
- **Timing:** GitHub can delay scheduled runs by 5–15 min under load — fine for
  hourly signals, but not second-precise.
- **Inactivity:** GitHub disables scheduled workflows after ~60 days with **no repo
  activity**. Any push (or clicking "Enable workflow") resets that.
- **State lives in `crypto_state.json` in the repo**, not on the runner — the runner
  is wiped after each run. The workflow commits the file back (only on a flip), which
  is what makes hourly continuity work. Don't delete that file.
- **Want more frequent alerts?** change the cron (e.g. `"*/15 * * * *"` for every
  15 min) and pass `--interval 15m`.

## Rotate your keys
The API keys currently sit in your local `.env`. Since they were on your laptop in
plaintext, consider rotating the Binance key and restricting it to **read-only**
(this bot only reads market data — it never places crypto trades).
