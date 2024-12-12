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
            # There is a previous utterance
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
            # First ever offense
            prev_user = None

        day_label = "day" if days_since_last == 1 else "days"

        if prev_user is None:
            # First offense ever
            message_text = (
                f"Alrightt! {username} just set the counter to start! Let's see how long we can go without saying his name again!"
            )
        else:
            if days_since_last == 0:
                # Check if less than 24 hours have passed
                t1, t2  # already defined above, we have delta
                if delta.total_seconds() < 86400:
                    # Extra sassy message for <24 hours
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We couldn’t even go 24 hours without saying his name??\n"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                        f"\"{prev_message}\""
                    )
                else:
                    # Same day but more than 24 hours
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.\n"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                        f"\"{prev_message}\""
                    )
            else:
                message_text = (
                    f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.\n"
                    f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                    f"\"{prev_message}\""
                )

        update.message.reply_text(message_text)

def leaderboard_command(update: Update, context: CallbackContext):
    data = get_leaderboard()
    if not data:
        update.message.reply_text("Wow, no one’s messed up yet! Who knew you were all so disciplined?")
        return
    msg = "The Hall of Shame:\n"
    for idx, row in enumerate(data, start=1):
        msg += f"{idx}. {row['username']}: {row['count']} times.\n"
    msg += "Seriously, guys. Get it together."
    update.message.reply_text(msg)

def recent_command(update: Update, context: CallbackContext):
    data = get_recent_utterances(limit=5)
    if not data:
        update.message.reply_text("No recent slip-ups. Congrats, you angels! Keep it that way.")
        return
    msg = "Check out these recent troublemakers:\n"
    for row in data:
        timestamp_str = datetime.fromisoformat(row['timestamp'].replace('Z','')).strftime("%d %b %Y %I:%M %p")
        timestamp_str = timestamp_str.replace("AM", "a.m.").replace("PM", "p.m.")
        msg += f"- {row['username']} at {timestamp_str}: {row['message_text']}\n"
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
    # updater.idle() can be omitted if it causes issues

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
