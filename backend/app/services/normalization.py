"""Shared form/chat boundary. All governed input passes this module."""
import re
from difflib import get_close_matches
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


FIELDS = {
    "leave": {"leave_type", "start_date", "end_date", "duration_days", "half_day", "reason", "contact_during_leave"},
    "reimbursement": {"category", "amount", "currency", "description", "receipt_ref"},
    "it_access": {"system_name", "access_level", "justification", "duration_days"},
}
REQUIRED = {
    "leave": ["leave_type", "start_date", "duration_days", "reason"],
    "reimbursement": ["category", "amount", "description"],
    "it_access": ["system_name", "access_level", "justification"],
}


def today_local():
    return datetime.now(ZoneInfo(get_settings().organization_timezone)).date()


DATE_WORDS = {
    "today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "january", "february",
    "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
}


def normalize_natural_date_spelling(value):
    """Correct an isolated, close spelling error in common English date words."""
    if not isinstance(value, str):
        return value
    words = re.split(r"(\W+)", value.lower())
    normalized = []
    for word in words:
        if not word.isalpha() or len(word) < 4 or word in DATE_WORDS:
            normalized.append(word)
            continue
        match = get_close_matches(word, DATE_WORDS, n=1, cutoff=0.82)
        normalized.append(match[0] if match else word)
    return "".join(normalized)


def working_days_inclusive(start, end):
    """Count Monday-Friday working days in an inclusive date range."""
    if end < start:
        raise ValueError("The end date is before the start date. Which dates should I use?")
    return sum(
        1 for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )


def end_date_for_working_days(start, duration):
    """Return the date containing the final requested Monday-Friday working day."""
    remaining = int(duration)
    current = start
    while True:
        if current.weekday() < 5:
            remaining -= 1
            if remaining == 0:
                return current
        current += timedelta(days=1)


def resolve_date(value, today=None):
    today = today or today_local()
    if not isinstance(value, str):
        raise ValueError("Please give a date or weekday.")
    value = normalize_natural_date_spelling(value).strip().rstrip(".")
    offsets = {"yesterday": -1, "today": 0, "aaj": 0, "aj": 0, "tomorrow": 1, "kal": 1, "day after tomorrow": 2, "parso": 2}
    if value in offsets:
        return today + timedelta(days=offsets[value])
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    weekday_match = re.fullmatch(r"(?:(next|this)\s+)?(" + "|".join(weekdays) + r")", value)
    if weekday_match:
        qualifier, weekday = weekday_match.groups()
        distance = (weekdays.index(weekday) - today.weekday()) % 7
        if qualifier == "next" and distance == 0:
            distance = 7
        return today + timedelta(days=distance)
    if re.fullmatch(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?", value):
        raise ValueError("ambiguous_numeric_date")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
        "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
        "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    month_names = "|".join(months)
    day_first = re.fullmatch(
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?:\s+(this year|\d{{4}}))?", value
    )
    month_first = re.fullmatch(
        rf"({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(this year|\d{{4}}))?", value
    )
    if day_first:
        day, month_name, year_text = day_first.groups()
    elif month_first:
        month_name, day, year_text = month_first.groups()
    else:
        raise ValueError("unrecognized_date")
    year = today.year if not year_text or year_text == "this year" else int(year_text)
    return date(year, months[month_name], int(day))


def normalize_leave_dates(fields, today=None):
    result = dict(fields)
    if not result.get("start_date"):
        return result
    start = resolve_date(result["start_date"], today)
    result["start_date"] = start.isoformat()
    end = resolve_date(result["end_date"], today) if result.get("end_date") else None
    raw_duration = result.get("duration_days")
    duration = None
    if raw_duration is not None:
        if isinstance(raw_duration, bool):
            raise ValueError("How many days do you need?")
        duration = float(raw_duration)
        if not (duration == 0.5 or duration.is_integer()) or not 0 < duration <= 366:
            raise ValueError("Please give a whole number of days, or a single half day (up to 366 days).")
    half = result.get("half_day", False)
    if not isinstance(half, bool):
        raise ValueError("Please clarify whether this is a half day.")
    if duration == 0.5:
        half = True
    if half and ((end and end != start) or (duration is not None and duration != 0.5)):
        raise ValueError("A half-day request must cover one date and a duration of half a day.")
    if end and end < start:
        raise ValueError("The end date is before the start date. Which dates should I use?")
    if half:
        end, duration = start, 0.5
    elif end:
        calculated = working_days_inclusive(start, end)
        if calculated == 0:
            raise ValueError("The selected range contains no working days. Please choose at least one weekday.")
        if duration is not None and duration != calculated:
            raise ValueError("The dates and number of days disagree. Please clarify the dates or duration.")
        duration = calculated
    elif duration is not None:
        end = end_date_for_working_days(start, duration)
    result["half_day"] = half
    if end:
        result["end_date"] = end.isoformat()
        result["duration_days"] = duration
    return result


def coherent_type(fields):
    """Only distinct business field families count; shared duration is not a type."""
    families = [kind for kind, names in FIELDS.items() if (set(fields) & (names - {"duration_days"}))]
    return families[0] if len(families) == 1 else None


def normalize_submission(request_type, data):
    from app.schemas.request import LeaveRequestData, ReimbursementRequestData, ITAccessRequestData
    schemas = {"leave": LeaveRequestData, "reimbursement": ReimbursementRequestData, "it_access": ITAccessRequestData}
    if request_type not in schemas:
        raise ValueError("Please choose leave, reimbursement, or IT access.")
    if set(data) - FIELDS[request_type]:
        raise ValueError("The supplied fields do not match this request type.")
    normalized = normalize_leave_dates(data) if request_type == "leave" else dict(data)
    if request_type == "reimbursement" and isinstance(normalized.get("amount"), str):
        # A currency marker is notation, not an exchange-rate calculation.
        amount_text = normalized["amount"].strip()
        match = re.fullmatch(r"(?:USD\s*|\$\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)", amount_text, re.IGNORECASE)
        if match:
            normalized["amount"] = float(match.group(1).replace(",", ""))
    for field in ("amount", "duration_days"):
        if isinstance(normalized.get(field), bool):
            raise ValueError(f"Please give a numeric {field.replace('_', ' ')}.")
    if request_type == "leave" and str(normalized.get("reason", "")).strip().lower() in {"yes", "no", "ok", "none", "n/a", "unknown", "because"}:
        raise ValueError("Please tell me a little more about the reason for your leave.")
    return schemas[request_type].model_validate(normalized).model_dump(mode="json", exclude_none=True)
