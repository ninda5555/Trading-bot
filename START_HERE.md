# 🙋 START HERE — for non-technical users

This guide assumes you know nothing about programming. Follow it top to bottom
once; after that, using the app is two double-clicks a day.

---

## 🗓️ DAY 1 — one-time setup (15 minutes)

### 1. Install Python 3.12 (the engine that runs the app)
⚠️ **Use Python 3.12 exactly — NOT the newest one.** The newest Python
(3.13/3.14) is too new for the Fyers broker library; 3.12 runs everything.

- **Windows:** download and run this installer:
  https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
- **Mac:** download "macOS 64-bit universal2 installer" from
  https://www.python.org/downloads/release/python-31210/
- On the first installer screen, tick **"Add Python to PATH"** if shown,
  then Install Now. (Already installed a newer Python? No problem — they
  live side by side; the launcher picks the right one automatically.)

### 2. Download this app
- On the GitHub page of this project, click the green **Code** button →
  **Download ZIP**.
- Unzip it anywhere you like (Desktop is fine). You'll get a folder called
  `Trading-bot`.

### 3. Start it
- **Windows:** open the folder and double-click **`START_DASHBOARD.bat`**
- **Mac:** double-click **`START_DASHBOARD.command`**
  (if Mac blocks it: right-click → Open → Open)
- A black window appears and does a few minutes of one-time setup, then your
  browser opens the dashboard by itself. **Keep the black window open** —
  it IS the app; closing it stops the dashboard.

🎉 That's it — you're looking at the dashboard in **Replay mode**: a practice
session so you can learn the screen with zero risk, any time of day.

### 4. (Optional, for real-time data) Connect your Fyers account
In the dashboard's **left sidebar**:
1. Open **"First-time setup: enter your Fyers app keys"**, paste your App ID
   and Secret key, click **Save**. (They're saved only on your computer.)
2. Click **"Step 1 · Open Fyers login page"** and log in with your Fyers ID,
   password and OTP.
3. The browser will land on a page that **looks broken** — an address starting
   with `https://127.0.0.1`. **That's normal.** Copy the whole address from
   the address bar.
4. Paste it into **Step 2** in the sidebar and click **Step 3 · Connect**.
5. Under **Data feed**, choose **live**. Done.

---

## ☀️ EVERY TRADING DAY — the 1-minute routine

1. Double-click **START_DASHBOARD** (if it isn't already running).
2. The sidebar will show **🔴 Not logged in today** — Fyers makes everyone
   log in fresh each day (a SEBI safety rule). Click the login link, log in,
   paste the address, click Connect. ~30 seconds.
3. Pick **live** under Data feed. Market opens at **9:15 AM**.

> ⏰ Do the login **after 7:00 AM** — tokens made in the middle of the night
> expire at 6 AM.

No Fyers account handy today? Pick **delayed** instead — free data, about a
minute behind. Fine for learning.

---

## 👀 HOW TO READ THE SCREEN (the 60-second version)

- **Top chips** — which way the overall market (NIFTY / BANK NIFTY) is leaning.
  Trading in the market's direction is swimming with the current.
- **Watchlist badges** — each stock gets a colour:
  - 🟢 **HIGH** = 4–5 of the 5 signals agree AND the 15-minute chart confirms.
    Rare and worth your attention.
  - 🟡 **MEDIUM** = close, but not confirmed. The disciplined move: wait.
  - ⚪ **LOW / NO SETUP** = noise. Do nothing. Doing nothing is a skill.
- **Click a stock** → live chart + a card that explains, in plain English,
  what the signals see and **what a sensible next step is** — always with a
  stop-loss idea and how many shares would risk only ~1% of your capital.
- **Trade Journal tab** — every HIGH signal is recorded and scored against
  what the price actually did 30/60 minutes later. Check it weekly; it's the
  honest report card.
- **Learn tab** — every jargon word explained simply.

---

## 🛡️ THE FOUR BEGINNER RULES (please actually follow these)

1. **Paper-trade first.** For at least 2–4 weeks, don't place real orders —
   just note what you *would* have done and let the Journal keep score.
2. **Never risk more than 1–2% per trade.** The app's quantity suggestion
   already does this math for you.
3. **Decide the stop-loss before entering, not after.** The app always shows
   one; if you can't accept that loss, skip the trade.
4. **Three losses in a day → stop for the day.** The app warns you at 3% of
   capital. Tomorrow always comes.

> ⚠️ This tool explains and suggests — it never guarantees. Most retail
> intraday traders lose money. Only ever trade money you can afford to lose.

---

## 🔧 If something breaks

- **Browser didn't open?** Type `localhost:8501` into your browser yourself.
- **"Login failed" when connecting Fyers?** Codes expire in seconds — click
  the login link again and paste the new address immediately.
- **Black window closed by accident?** Just double-click START_DASHBOARD again.
- Anything else: copy the error text from the black window and ask for help.
