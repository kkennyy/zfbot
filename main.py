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

        # Default values for no previous offense
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

            # Format timestamp: "dd MMM yyyy hh:mm a.m./p.m."
            timestamp_str = t2.strftime("%d %b %Y %I:%M %p")
            # Convert AM/PM to a.m./p.m.
            timestamp_str = timestamp_str.replace("AM", "a.m.").replace("PM", "p.m.")
            prev_time_str = timestamp_str
        else:
            # This is the very first forbidden word utterance, so no previous offender
            prev_user = None

        # Determine whether to say "day" or "days"
        day_label = "day" if days_since_last == 1 else "days"

        if prev_user is None:
            # First offense ever
            message_text = (
                f"Alrighttt! {username} just started us off with the first instance of his name!"
                f"Let's see how long we can go without saying his name again!"
            )
        else:
            # Not the first offense
            if days_since_last == 0:
                # Means less than a day; but let's confirm using total seconds for extra sass
                # If previous utterance was less than 24 hours ago
                if (delta.total_seconds() < 86400):
                    # Extra sassy message for <24 hours
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We couldn’t even go 24 hours without saying his name??\n"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                        f"\"{prev_message}\""
                    )
                else:
                    # If it’s 0 days due to same date but more than 24 hours (unlikely, but just in case)
                    message_text = (
                        f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.\n"
                        f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                        f"\"{prev_message}\""
                    )
            else:
                # days_since_last >= 1
                message_text = (
                    f"Jialat! {username} just ruined the streak. We made it {days_since_last} {day_label} since the last slip-up.\n"
                    f"Previously, {prev_user} messed up on {prev_time_str} with:\n"
                    f"\"{prev_message}\""
                )

        update.message.reply_text(message_text)
