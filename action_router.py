import re
from datetime import datetime, timedelta, timezone


def normalize_command(message):
    command = re.sub(r"^priya[,\s]+", "", message.strip(), flags=re.IGNORECASE)
    command = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", command, flags=re.IGNORECASE)
    command = re.sub(r"[.?!]+$", "", command).strip()
    command = re.sub(r"\s+(?:for me|please|priya)$", "", command, flags=re.IGNORECASE).strip()
    command = re.sub(r"^(?:add|create) (?:a )?task (?:to )?", "add task ", command, flags=re.IGNORECASE)
    return command


def reminder_task(command, now=None):
    match = re.fullmatch(
        r"remind me in ([\w.]+) (seconds?|minutes?|hours?|days?) to (.+)",
        command, flags=re.IGNORECASE,
    )
    if not match:
        return None
    words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
             "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    amount = words.get(match[1].lower())
    if amount is None:
        try:
            amount = float(match[1])
        except ValueError as error:
            raise ValueError("Use a number, for example 'remind me in 2 minutes to drink water'.") from error
    seconds = amount * {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[match[2].lower().rstrip("s")]
    if not 1 <= seconds <= 366 * 86400:
        raise ValueError("Reminders must be between one second and 366 days from now.")
    return {"title": match[3], "due": ((now or datetime.now(timezone.utc)) + timedelta(seconds=seconds)).isoformat()}


def unsupported_action(command):
    return bool(re.search(
        r"\b(?:remind me|set (?:an? )?(?:alarm|reminder)|schedule|send (?:an? |the |my )?(?:email|message)|"
        r"forward (?:an? |the |my )?email|delete (?:my |the )?files?|shut ?down|turn (?:on|off)|"
        r"(?:add|create|save) (?:a |my )?task)\b",
        command, flags=re.IGNORECASE,
    ))
