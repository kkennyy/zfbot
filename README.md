
# zfbot Setup Guide

This guide provides a comprehensive walkthrough to set up **zfbot**—a Telegram bot that tracks the usage of certain forbidden words in a Telegram group chat. The bot logs offenders into a Supabase database, resets a “days since last utterance” counter, and provides commands for viewing a leaderboard and recent offenses.

## Overview

**What Does zfbot Do?**  
- Monitors a Telegram group for forbidden words (e.g., “zf”, “zhefei”).  
- Logs each offense (who said it, what was said, when).  
- Announces how many days since the last offense and resets the counter whenever forbidden words are uttered.
- Provides two commands:
  - `/leaderboard`: Shows top offenders.
  - `/recent`: Shows recent offenses with timestamps.

**Key Features**:
- Entirely cloud-based (no local machine needed).
- Uses a dummy HTTP server to keep the hosting service’s Web Service “healthy.”
- Employs Supabase for database storage.
- Written in Python using `python-telegram-bot`.

## Infrastructure and Services

1. **Telegram Bot**:
   - Create via [BotFather](https://t.me/BotFather).
   - Obtain a bot token.
   - Disable Privacy Mode so the bot can read all messages.

2. **Supabase**:
   - Sign up at [https://supabase.com](https://supabase.com).
   - Note `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
   - Create a table and a leaderboard function (SQL provided below).

3. **Render (Free Tier)**:
   - Host your bot code as a Web Service at [https://render.com](https://render.com).
   - Connect your GitHub repo.
   - Add environment variables for the bot token and Supabase keys.

4. **GitHub**:
   - Store code in a GitHub repository.
   - Render pulls code from here for deployment.

## Database Schema (Supabase)

Use the SQL editor in Supabase to create the table:

```sql
CREATE TABLE public.utterances (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id bigint NOT NULL,
  username text NOT NULL,
  message_text text NOT NULL,
  chat_id bigint,
  message_id bigint,
  timestamp timestamptz NOT NULL DEFAULT now()
);
```

Create the leaderboard function:

```sql
CREATE OR REPLACE FUNCTION public.leaderboard()
RETURNS TABLE(username text, count bigint) AS $$
SELECT username, COUNT(*) AS count
FROM public.utterances
GROUP BY username
ORDER BY count DESC;
$$ LANGUAGE sql STABLE;
```

**To clear all data:**
```sql
TRUNCATE TABLE public.utterances;
```

## Code and Dependencies

**requirements.txt**:
```
python-telegram-bot==13.15
requests
supabase-py
```

**main.py** (Adjust forbidden words and messages as desired):

```python
import os
import threading
import http.server
import socketserver
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackContext
import requests
import json

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

FORBIDDEN_WORDS = ["zf", "zhefei"]

def insert_utterance(user_id, username, message_text, chat_id, message_id):
    url = f"{SUPABASE_URL}/rest/v1/utterances"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    data = {
        "user_id": user_id,
        "username": username,
        "message_text": message_text,
        "chat_id": chat_id,
        "message_id": message_id
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()

def get_leaderboard():
    url = f"{SUPABASE_URL}/rest/v1/rpc/leaderboard"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_recent_utterances(limit=5):
    url = f"{SUPABASE_URL}/rest/v1/utterances?select=username,message_text,timestamp,chat_id,message_id&order=timestamp.desc&limit={limit}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def message_handler(update: Update, context: CallbackContext):
    if update.message is None or update.message.text is None:
        return
    text = update.message.text.lower()
    if any(word in text for word in FORBIDDEN_WORDS):
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        chat_id = update.message.chat_id
        message_id = update.message.message_id

        insert_utterance(user_id, username, update.message.text, chat_id, message_id)

        recent = get_recent_utterances(limit=2)
        days_since_last = 0
        prev_user = None
        prev_message = ""
        prev_time_str = ""

        if len(recent) == 2:
            t1 = datetime.fromisoformat(recent[0]['timestamp'].replace('Z',''))
            t2 = datetime.fromisoformat(recent[1]['timestamp'].replace('Z',''))
            delta = t1 - t2
            days_since_last = delta.days
            prev_user = recent[1]['username']
            prev_message = recent[1]['message_text']

            timestamp_str = t2.strftime("%d %b %Y %I:%M %p")
            timestamp_str = timestamp_str.replace("AM", "a.m.").replace("PM", "p.m.")
            prev_time_str = timestamp_str
        else:
            prev_user = None

        day_label = "day" if days_since_last == 1 else "days"

        if prev_user is None:
            message_text = (
                f"Alrightt! {username} just set the counter to start! Let's see how long we can go without saying his name again!"
            )
        else:
            if days_since_last == 0:
                if delta.total_seconds() < 86400:
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We couldn’t even go 24 hours without saying his name??
"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:
"
                        f""{prev_message}""
                    )
                else:
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.
"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:
"
                        f""{prev_message}""
                    )
            else:
                message_text = (
                    f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.
"
                    f"Previously, {prev_user} messed up on {prev_time_str} with:
"
                    f""{prev_message}""
                )

        update.message.reply_text(message_text)

def leaderboard_command(update: Update, context: CallbackContext):
    data = get_leaderboard()
    if not data:
        update.message.reply_text("Wow, no one’s messed up yet! Who knew you were all so disciplined?")
        return
    msg = "The Hall of Shame:
"
    for idx, row in enumerate(data, start=1):
        msg += f"{idx}. {row['username']}: {row['count']} times.
"
    msg += "Seriously, guys. Get it together."
    update.message.reply_text(msg)

def recent_command(update: Update, context: CallbackContext):
    data = get_recent_utterances(limit=5)
    if not data:
        update.message.reply_text("No recent slip-ups. Congrats, you angels! Keep it that way.")
        return
    msg = "Check out these recent troublemakers:
"
    for row in data:
        timestamp_str = datetime.fromisoformat(row['timestamp'].replace('Z','')).strftime("%d %b %Y %I:%M %p")
        timestamp_str = timestamp_str.replace("AM", "a.m.").replace("PM", "p.m.")
        msg += f"- {row['username']} at {timestamp_str}: {row['message_text']}
"
    msg += "Tsk, tsk."
    update.message.reply_text(msg)

def run_bot():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dp.add_handler(CommandHandler("leaderboard", leaderboard_command))
    dp.add_handler(CommandHandler("recent", recent_command))

    print("Bot is starting up...")
    updater.start_polling()

def run_server():
    port = int(os.environ.get('PORT', 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("HTTP server running on port:", port)
        httpd.serve_forever()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_server()
```

## Environment Variables

Set these in Render’s “Environment” tab (or equivalent):

- `TELEGRAM_TOKEN` = `<your_bot_token>`
- `SUPABASE_URL` = `<your_supabase_url>`
- `SUPABASE_ANON_KEY` = `<your_supabase_anon_key>`

## Hosting on Render

1. Push the code to GitHub.
2. On Render: “New” > “Web Service” > Select your GitHub repo.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python main.py`
5. Add environment variables.
6. Deploy. Render runs the HTTP server and the bot together.

## Telegram Configuration

1. In BotFather:  
   - `/mybots` > Select your bot  
   - **Bot Settings** > **Group Privacy** > Disable.
2. Add the bot to your Telegram group.
3. Test by typing the forbidden words.

If it doesn’t respond:
- Remove and re-add the bot after disabling privacy.
- Check if the group is a supergroup.
- Review Render logs.

## Commands

- **`/leaderboard`**: Shows top offenders.
- **`/recent`**: Lists recent offenses.

## Maintenance

- **Updating Code**: Commit changes to GitHub; redeploy on Render.
- **Clearing Data**: Run `TRUNCATE TABLE public.utterances;` in Supabase SQL editor.
- **Testing**: Test in a separate group or chat first.

---

This README details every step—from database schema to environment variables, code deployment, and bot configuration.
