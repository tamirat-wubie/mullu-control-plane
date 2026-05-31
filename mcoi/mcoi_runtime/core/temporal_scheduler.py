"""Purpose: in-memory temporal action scheduler.
Governance scope: deferred temporal action admission, lease control, policy
    re-check, run receipts, and missed/expired action closure.
Dependencies: temporal_runtime engine and temporal_runtime contracts.
Invariants:
  - Scheduled actions never become due before execute_at.
  - Expired actions are closed instead of executed.
  - Leases prevent duplicate worker execution.
  - Temporal policy is re-checked at wake time.
  - Every due evaluation emits a bounded receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcoi_runtime.contracts.temporal_runtime import (
    TemporalActionDecision,
    TemporalActionRequest,
    TemporalPolicyVerdict,
    TemporalSkillExecutionVerdict,
    TemporalSkillPlanExecution,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_skill_executor import TemporalSkillPlanExecutor, TemporalSkillStageProvider


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _normalize_temporal_phrase(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _resolve_relative_phrase(now: datetime, amount: int, unit: str) -> tuple[str, str]:
    minute_units = {
        "minute",
        "minutes",
        "minuut",
        "minuten",
        "minut",
        "minuter",
        "minutt",
        "minutter",
        "minuutti",
        "minuuttia",
        "minuta",
        "minuty",
        "minutu",
        "perc",
        "dakika",
        "menit",
    }
    hour_units = {
        "hour",
        "hours",
        "uur",
        "uren",
        "timme",
        "timmar",
        "time",
        "timer",
        "tunti",
        "tuntia",
        "godzina",
        "godzine",
        "godziny",
        "godzin",
        "hodinu",
        "hodiny",
        "hodin",
        "ora",
        "ore",
        "saat",
        "jam",
    }
    day_units = {
        "day",
        "days",
        "dag",
        "dagen",
        "dagar",
        "dage",
        "dager",
        "paiva",
        "paivaa",
        "dzien",
        "dni",
        "den",
        "dny",
        "nap",
        "zi",
        "zile",
        "gun",
        "hari",
    }
    if unit in minute_units:
        delta = timedelta(minutes=amount)
    elif unit in hour_units:
        delta = timedelta(hours=amount)
    elif unit in day_units:
        delta = timedelta(days=amount)
    else:
        return "", "temporal_phrase_unsupported"
    return _iso(now + delta), "temporal_phrase_exact_relative"


def _timezone_for_mode(mode: str, original_timezone: str) -> timezone | ZoneInfo:
    if mode in {"utc", "z"}:
        return timezone.utc
    if not original_timezone:
        return timezone.utc
    try:
        return ZoneInfo(original_timezone)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeCoreInvariantError("temporal_phrase_original_timezone_invalid") from exc


def _resolve_relative_wall_time(
    now: datetime,
    *,
    original_timezone: str,
    day_offset: int,
    hour: int,
    minute: int,
    mode: str,
) -> tuple[str, str]:
    if hour > 23 or minute > 59:
        return "", "temporal_phrase_invalid_wall_time"
    zone = _timezone_for_mode(mode, original_timezone)
    local_now = now.astimezone(zone)
    target_date = local_now.date() + timedelta(days=day_offset)
    target = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=zone)
    reason = "temporal_phrase_exact_local_wall_time" if mode == "local" else "temporal_phrase_exact_utc_wall_time"
    return _iso(target), reason


def _resolve_next_weekday_wall_time(
    now: datetime,
    *,
    original_timezone: str,
    weekday: int,
    hour: int,
    minute: int,
    mode: str,
) -> tuple[str, str]:
    if hour > 23 or minute > 59:
        return "", "temporal_phrase_invalid_wall_time"
    zone = _timezone_for_mode(mode, original_timezone)
    local_now = now.astimezone(zone)
    days_ahead = (weekday - local_now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = local_now.date() + timedelta(days=days_ahead)
    target = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=zone)
    reason = "temporal_phrase_exact_local_weekday_wall_time" if mode == "local" else "temporal_phrase_exact_utc_weekday_wall_time"
    return _iso(target), reason


def _english_weekdays() -> dict[str, int]:
    return {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def _dutch_weekdays() -> dict[str, int]:
    return {"maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}


def _swedish_weekdays() -> dict[str, int]:
    return {"mandag": 0, "tisdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lordag": 5, "sondag": 6}


def _danish_weekdays() -> dict[str, int]:
    return {"mandag": 0, "tirsdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lordag": 5, "sondag": 6}


def _norwegian_weekdays() -> dict[str, int]:
    return {"mandag": 0, "tirsdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lordag": 5, "sondag": 6}


def _finnish_weekdays() -> dict[str, int]:
    return {
        "maanantai": 0,
        "tiistai": 1,
        "keskiviikko": 2,
        "torstai": 3,
        "perjantai": 4,
        "lauantai": 5,
        "sunnuntai": 6,
    }


def _polish_weekdays() -> dict[str, int]:
    return {
        "poniedzialek": 0,
        "wtorek": 1,
        "sroda": 2,
        "czwartek": 3,
        "piatek": 4,
        "sobota": 5,
        "niedziela": 6,
    }


def _czech_weekdays() -> dict[str, int]:
    return {"pondeli": 0, "utery": 1, "streda": 2, "ctvrtek": 3, "patek": 4, "sobota": 5, "nedele": 6}


def _slovak_weekdays() -> dict[str, int]:
    return {"pondelok": 0, "utorok": 1, "streda": 2, "stvrtok": 3, "piatok": 4, "sobota": 5, "nedela": 6}


def _hungarian_weekdays() -> dict[str, int]:
    return {
        "hetfo": 0,
        "kedd": 1,
        "szerda": 2,
        "csutortok": 3,
        "pentek": 4,
        "szombat": 5,
        "vasarnap": 6,
    }


def _romanian_weekdays() -> dict[str, int]:
    return {
        "luni": 0,
        "marti": 1,
        "miercuri": 2,
        "joi": 3,
        "vineri": 4,
        "sambata": 5,
        "duminica": 6,
    }


def _turkish_weekdays() -> dict[str, int]:
    return {
        "pazartesi": 0,
        "sali": 1,
        "carsamba": 2,
        "persembe": 3,
        "cuma": 4,
        "cumartesi": 5,
        "pazar": 6,
    }


def _indonesian_weekdays() -> dict[str, int]:
    return {
        "senin": 0,
        "selasa": 1,
        "rabu": 2,
        "kamis": 3,
        "jumat": 4,
        "sabtu": 5,
        "minggu": 6,
    }


def _resolve_bounded_temporal_phrase(
    phrase: str,
    *,
    locale: str,
    now: str,
    original_timezone: str,
) -> tuple[str, str, str]:
    normalized = _normalize_temporal_phrase(phrase)
    now_dt = _parse_iso(now)
    locale_key = locale.strip().lower()
    if locale_key in {"en", "en-us", "en-gb"}:
        return _resolve_english_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"nl", "nl-nl", "nl-be"}:
        return _resolve_dutch_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sv", "sv-se", "sv-fi"}:
        return _resolve_swedish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"da", "da-dk", "da-gl"}:
        return _resolve_danish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"no", "no-no", "nb", "nb-no", "nn", "nn-no"}:
        return _resolve_norwegian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"fi", "fi-fi"}:
        return _resolve_finnish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"pl", "pl-pl"}:
        return _resolve_polish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"cs", "cs-cz"}:
        return _resolve_czech_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sk", "sk-sk"}:
        return _resolve_slovak_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"hu", "hu-hu"}:
        return _resolve_hungarian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"ro", "ro-ro", "ro-md"}:
        return _resolve_romanian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"tr", "tr-tr", "tr-cy"}:
        return _resolve_turkish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"id", "id-id"}:
        return _resolve_indonesian_temporal_phrase(normalized, now_dt, original_timezone)
    return "unsupported", "temporal_phrase_locale_not_supported", ""


def _resolve_english_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"in ([1-9][0-9]*) (minute|minutes|hour|hours|day|days)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(today|tomorrow) at ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "tomorrow" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"next (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_english_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"today", "tomorrow", "tonight", "later", "soon", "next week", "next month", "next year"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_dutch_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"over ([1-9][0-9]*) (minuut|minuten|uur|uren|dag|dagen)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(vandaag|morgen) om ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "morgen" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"volgende (maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag) om ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_dutch_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"vandaag", "morgen", "vanavond", "later", "binnenkort", "volgende week", "volgende maand", "volgend jaar"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_swedish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"om ([1-9][0-9]*) (minut|minuter|timme|timmar|dag|dagar)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(idag|imorgon) klockan ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "imorgon" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"nasta (mandag|tisdag|onsdag|torsdag|fredag|lordag|sondag) klockan ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_swedish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"idag", "imorgon", "ikvall", "senare", "snart", "nasta vecka", "nasta manad", "nasta ar"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_danish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"om ([1-9][0-9]*) (minut|minutter|time|timer|dag|dage)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(i dag|i morgen) klokken ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "i morgen" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"naeste (mandag|tirsdag|onsdag|torsdag|fredag|lordag|sondag) klokken ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_danish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"i dag", "i morgen", "i aften", "senere", "snart", "naeste uge", "naeste maned", "naeste ar"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"naeste (mandag|tirsdag|onsdag|torsdag|fredag|lordag|sondag)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_norwegian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"om ([1-9][0-9]*) (minutt|minutter|time|timer|dag|dager)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(i dag|i morgen) klokken ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "i morgen" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"neste (mandag|tirsdag|onsdag|torsdag|fredag|lordag|sondag) klokken ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_norwegian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"i dag", "i morgen", "i kveld", "senere", "snart", "neste uke", "neste maned", "neste ar"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"neste (mandag|tirsdag|onsdag|torsdag|fredag|lordag|sondag)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_finnish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"([1-9][0-9]*) (minuutti|minuuttia|tunti|tuntia|paiva|paivaa) kuluttua", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(tanaan|huomenna) kello ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "huomenna" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"ensi (maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai) kello ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_finnish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"tanaan", "huomenna", "tana iltana", "myohemmin", "pian", "ensi viikko", "ensi kuukausi", "ensi vuosi"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"ensi (maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_polish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minuta|minuty|minut|godzina|godzine|godziny|godzin|dzien|dni)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(dzisiaj|jutro) o ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "jutro" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"nastepny (poniedzialek|wtorek|sroda|czwartek|piatek|sobota|niedziela) o ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_polish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"dzisiaj", "jutro", "dzis wieczorem", "pozniej", "wkrotce", "nastepny tydzien", "nastepny miesiac", "nastepny rok"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"nastepny (poniedzialek|wtorek|sroda|czwartek|piatek|sobota|niedziela)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_czech_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minutu|minuty|minut|hodinu|hodiny|hodin|den|dny|dni)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(dnes|zitra) v ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "zitra" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"pristi (pondeli|utery|streda|ctvrtek|patek|sobota|nedele) v ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_czech_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"dnes", "zitra", "dnes vecer", "pozdeji", "brzy", "pristi tyden", "pristi mesic", "pristi rok"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"pristi (pondeli|utery|streda|ctvrtek|patek|sobota|nedele)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_slovak_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minutu|minuty|minut|hodinu|hodiny|hodin|den|dni)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(dnes|zajtra) o ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "zajtra" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"buduci (pondelok|utorok|streda|stvrtok|piatok|sobota|nedela) o ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_slovak_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"dnes", "zajtra", "dnes vecer", "neskor", "coskoro", "buduci tyzden", "buduci mesiac", "buduci rok"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"buduci (pondelok|utorok|streda|stvrtok|piatok|sobota|nedela)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_hungarian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"([1-9][0-9]*) (perc|ora|nap) mulva", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(ma|holnap) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "holnap" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"kovetkezo (hetfo|kedd|szerda|csutortok|pentek|szombat|vasarnap) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_hungarian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"ma", "holnap", "ma este", "kesobb", "hamarosan", "jovo het", "jovo honap", "jovo ev"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"kovetkezo (hetfo|kedd|szerda|csutortok|pentek|szombat|vasarnap)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_romanian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"peste ([1-9][0-9]*) (minut|minute|ora|ore|zi|zile)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(azi|maine) la ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "maine" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"urmatoarea (luni|marti|miercuri|joi|vineri|sambata|duminica) la ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_romanian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "azi",
        "maine",
        "diseara",
        "mai tarziu",
        "curand",
        "saptamana viitoare",
        "luna viitoare",
        "anul viitor",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"urmatoarea (luni|marti|miercuri|joi|vineri|sambata|duminica)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_turkish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"([1-9][0-9]*) (dakika|saat|gun) sonra", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(bugun|yarin) saat ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "yarin" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"gelecek (pazartesi|sali|carsamba|persembe|cuma|cumartesi|pazar) saat ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_turkish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"bugun", "yarin", "bu aksam", "sonra", "yakinda", "gelecek hafta", "gelecek ay", "gelecek yil"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"gelecek (pazartesi|sali|carsamba|persembe|cuma|cumartesi|pazar)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_indonesian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"dalam ([1-9][0-9]*) (menit|jam|hari)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hari ini|besok) pukul ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "besok" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(senin|selasa|rabu|kamis|jumat|sabtu|minggu) depan pukul ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_indonesian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"hari ini", "besok", "nanti malam", "nanti", "segera", "minggu depan", "bulan depan", "tahun depan"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"(senin|selasa|rabu|kamis|jumat|sabtu|minggu) depan", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


class ScheduledActionState(StrEnum):
    """Lifecycle state for a scheduled temporal action."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    MISSED = "missed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleDecisionVerdict(StrEnum):
    """Scheduler decision for a due-action evaluation."""

    DUE = "due"
    NOT_DUE = "not_due"
    LEASED = "leased"
    COMPLETED = "completed"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ScheduledTemporalAction:
    """Deferred temporal action waiting for governed wake-time evaluation."""

    schedule_id: str
    tenant_id: str
    action: TemporalActionRequest
    execute_at: str
    state: ScheduledActionState = ScheduledActionState.PENDING
    handler_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TemporalLease:
    """Worker lease for one scheduled temporal action."""

    lease_id: str
    schedule_id: str
    worker_id: str
    acquired_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class TemporalRunReceipt:
    """Bounded receipt for a scheduler evaluation or state closure."""

    receipt_id: str
    schedule_id: str
    tenant_id: str
    verdict: ScheduleDecisionVerdict
    reason: str
    evaluated_at: str
    worker_id: str = ""
    temporal_decision_id: str = ""
    temporal_verdict: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TemporalSchedulerEngine:
    """In-memory scheduler for deferred temporal actions."""

    def __init__(
        self,
        temporal_runtime: TemporalRuntimeEngine,
        *,
        clock: Any,
        skill_stage_provider: TemporalSkillStageProvider | None = None,
    ) -> None:
        if not isinstance(temporal_runtime, TemporalRuntimeEngine):
            raise RuntimeCoreInvariantError("temporal_runtime must be a TemporalRuntimeEngine")
        self._temporal_runtime = temporal_runtime
        self._clock = clock
        self._skill_stage_provider = skill_stage_provider
        self._actions: dict[str, ScheduledTemporalAction] = {}
        self._leases: dict[str, TemporalLease] = {}
        self._receipts: list[TemporalRunReceipt] = []
        self._skill_plan_executions: dict[str, TemporalSkillPlanExecution] = {}

    @property
    def action_count(self) -> int:
        return len(self._actions)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def skill_plan_execution_count(self) -> int:
        return len(self._skill_plan_executions)

    def register(
        self,
        schedule_id: str,
        action: TemporalActionRequest,
        *,
        handler_name: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ScheduledTemporalAction:
        """Register a deferred temporal action."""
        if schedule_id in self._actions:
            raise RuntimeCoreInvariantError("Duplicate schedule_id")
        if not isinstance(action, TemporalActionRequest):
            raise RuntimeCoreInvariantError("action must be a TemporalActionRequest")
        now = self._clock()
        action = self._admit_temporal_phrase(action, now)
        if not action.execute_at:
            raise RuntimeCoreInvariantError("execute_at is required")

        scheduled = ScheduledTemporalAction(
            schedule_id=schedule_id,
            tenant_id=action.tenant_id,
            action=action,
            execute_at=action.execute_at,
            handler_name=handler_name,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self._actions[schedule_id] = scheduled
        return scheduled

    def _admit_temporal_phrase(self, action: TemporalActionRequest, now: str) -> TemporalActionRequest:
        if not action.temporal_phrase:
            return action
        verdict, reason, resolved_execute_at = _resolve_bounded_temporal_phrase(
            action.temporal_phrase,
            locale=action.temporal_phrase_locale,
            now=now,
            original_timezone=str(action.metadata.get("original_timezone", "")),
        )
        if verdict != "exact":
            if action.temporal_phrase_policy == "operator_review":
                raise RuntimeCoreInvariantError("temporal_phrase_operator_review_required")
            if action.temporal_phrase_policy == "require_exact":
                raise RuntimeCoreInvariantError(reason)
            return action
        metadata = {
            **dict(action.metadata),
            "temporal_phrase_admission_verdict": verdict,
            "temporal_phrase_admission_reason": reason,
            "temporal_phrase_resolved_execute_at": resolved_execute_at,
        }
        if action.execute_at and _iso(_parse_iso(action.execute_at)) != resolved_execute_at:
            raise RuntimeCoreInvariantError("temporal_phrase_execute_at_mismatch")
        return replace(action, execute_at=resolved_execute_at, metadata=metadata)

    def get(self, schedule_id: str) -> ScheduledTemporalAction:
        """Return a scheduled action by id."""
        action = self._actions.get(schedule_id)
        if action is None:
            raise RuntimeCoreInvariantError("Unknown schedule_id")
        return action

    def restore(self, actions: tuple[ScheduledTemporalAction, ...]) -> None:
        """Restore scheduled action snapshots into an empty scheduler."""
        if self._actions or self._leases or self._receipts:
            raise RuntimeCoreInvariantError("restore requires an empty scheduler")
        for action in actions:
            if not isinstance(action, ScheduledTemporalAction):
                raise RuntimeCoreInvariantError("restore item must be a ScheduledTemporalAction")
            if action.schedule_id in self._actions:
                raise RuntimeCoreInvariantError("duplicate restored schedule_id")
            self._actions[action.schedule_id] = action

    def due_actions(self, now: str | None = None) -> tuple[ScheduledTemporalAction, ...]:
        """Return pending actions due at or before now."""
        now_dt = _parse_iso(now or self._clock())
        due: list[ScheduledTemporalAction] = []
        for action in self._actions.values():
            if action.state is not ScheduledActionState.PENDING:
                continue
            if self._active_lease(action.schedule_id, now_dt) is not None:
                continue
            if action.action.expires_at and now_dt > _parse_iso(action.action.expires_at):
                continue
            if _parse_iso(action.execute_at) <= now_dt:
                due.append(action)
        return tuple(sorted(due, key=lambda item: item.schedule_id))

    def acquire_lease(
        self,
        schedule_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 60,
    ) -> TemporalLease | None:
        """Acquire a lease for a due pending action."""
        action = self.get(schedule_id)
        now_text = self._clock()
        now_dt = _parse_iso(now_text)
        if action.state is not ScheduledActionState.PENDING:
            return None
        if _parse_iso(action.execute_at) > now_dt:
            return None
        if self._active_lease(schedule_id, now_dt) is not None:
            return None

        lease = TemporalLease(
            lease_id=stable_identifier(
                "temp-lease",
                {"schedule_id": schedule_id, "worker_id": worker_id, "at": now_text},
            ),
            schedule_id=schedule_id,
            worker_id=worker_id,
            acquired_at=now_text,
            expires_at=_iso(now_dt + timedelta(seconds=lease_seconds)),
        )
        self._leases[schedule_id] = lease
        self._replace_action(action, ScheduledActionState.RUNNING)
        return lease

    def evaluate_due_action(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Re-check temporal policy for a due action and emit a receipt."""
        action = self.get(schedule_id)
        now = self._clock()
        now_dt = _parse_iso(now)

        if action.state is ScheduledActionState.COMPLETED:
            return self._record(action, ScheduleDecisionVerdict.COMPLETED, "already_completed", now, worker_id)
        if action.state is ScheduledActionState.EXPIRED:
            return self._record(action, ScheduleDecisionVerdict.EXPIRED, "already_expired", now, worker_id)
        if action.state is ScheduledActionState.PENDING and _parse_iso(action.execute_at) > now_dt:
            return self._record(action, ScheduleDecisionVerdict.NOT_DUE, "not_due", now, worker_id)
        if action.action.expires_at and now_dt > _parse_iso(action.action.expires_at):
            self._replace_action(action, ScheduledActionState.EXPIRED)
            return self._record(action, ScheduleDecisionVerdict.EXPIRED, "command_expired", now, worker_id)

        decision = self._temporal_runtime.decide_temporal_action(action.action)
        if decision.verdict is TemporalPolicyVerdict.ALLOW:
            return self._record_temporal(
                action, decision, ScheduleDecisionVerdict.DUE, "temporal_policy_passed", now, worker_id
            )
        if decision.verdict is TemporalPolicyVerdict.DEFER:
            self._replace_action(action, ScheduledActionState.PENDING)
            return self._record_temporal(
                action, decision, ScheduleDecisionVerdict.NOT_DUE, decision.reason, now, worker_id
            )

        self._replace_action(action, ScheduledActionState.BLOCKED)
        return self._record_temporal(
            action, decision, ScheduleDecisionVerdict.BLOCKED, decision.reason, now, worker_id
        )

    def mark_completed(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action completed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.COMPLETED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.COMPLETED, "completed", self._clock(), worker_id)

    def execute_skill_plan(self, schedule_id: str, *, worker_id: str = "") -> TemporalSkillPlanExecution:
        """Execute a bound temporal skill plan through the configured provider."""

        if schedule_id in self._skill_plan_executions:
            return self._skill_plan_executions[schedule_id]
        action = self.get(schedule_id)
        if action.action.skill_plan is None:
            raise RuntimeCoreInvariantError("skill_plan is required")
        if action.state is not ScheduledActionState.RUNNING:
            raise RuntimeCoreInvariantError("schedule must be running before skill plan execution")
        if self._skill_stage_provider is None:
            raise RuntimeCoreInvariantError("skill_stage_provider is required")
        execution = TemporalSkillPlanExecutor(self._skill_stage_provider, clock=self._clock).execute(
            action.action.skill_plan,
            schedule_ref=schedule_id,
        )
        self._skill_plan_executions[schedule_id] = execution
        metadata = {
            "skill_plan_execution_id": execution.execution_id,
            "skill_plan_execution_verdict": execution.verdict.value,
            "skill_plan_execution_reason": execution.reason,
            "worker_id": worker_id,
        }
        if execution.verdict is TemporalSkillExecutionVerdict.PASS:
            self._replace_action(action, ScheduledActionState.COMPLETED, metadata={**dict(action.metadata), **metadata})
            self._leases.pop(schedule_id, None)
            self._record(
                self.get(schedule_id),
                ScheduleDecisionVerdict.COMPLETED,
                "skill_plan_executed",
                self._clock(),
                worker_id,
            )
            return execution
        self._replace_action(action, ScheduledActionState.BLOCKED, metadata={**dict(action.metadata), **metadata})
        self._leases.pop(schedule_id, None)
        self._record(self.get(schedule_id), ScheduleDecisionVerdict.BLOCKED, execution.reason, self._clock(), worker_id)
        return execution

    def mark_failed(
        self,
        schedule_id: str,
        *,
        worker_id: str = "",
        reason: str = "failed",
    ) -> TemporalRunReceipt:
        """Mark a scheduled action failed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.FAILED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.BLOCKED, reason, self._clock(), worker_id)

    def mark_missed(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action missed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.MISSED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.BLOCKED, "missed_run", self._clock(), worker_id)

    def mark_cancelled(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action cancelled and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.CANCELLED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.BLOCKED, "cancelled", self._clock(), worker_id)

    def release_lease(self, schedule_id: str) -> bool:
        """Release a lease and return a running action to pending."""
        action = self.get(schedule_id)
        removed = self._leases.pop(schedule_id, None)
        if removed is None:
            return False
        if action.state is ScheduledActionState.RUNNING:
            self._replace_action(action, ScheduledActionState.PENDING)
        return True

    def recent_receipts(self, limit: int = 50) -> tuple[TemporalRunReceipt, ...]:
        """Return recent scheduler receipts newest first."""
        return tuple(reversed(self._receipts[-limit:]))

    def summary(self) -> dict[str, int]:
        """Return bounded scheduler counters for observability."""
        counts = {state.value: 0 for state in ScheduledActionState}
        for action in self._actions.values():
            counts[action.state.value] += 1
        return {
            "actions": len(self._actions),
            "receipts": len(self._receipts),
            "leases": len(self._leases),
            "skill_plan_executions": len(self._skill_plan_executions),
            **counts,
        }

    def _active_lease(self, schedule_id: str, now_dt: datetime) -> TemporalLease | None:
        lease = self._leases.get(schedule_id)
        if lease is None:
            return None
        if _parse_iso(lease.expires_at) <= now_dt:
            self._leases.pop(schedule_id, None)
            action = self._actions.get(schedule_id)
            if action is not None and action.state is ScheduledActionState.RUNNING:
                self._replace_action(action, ScheduledActionState.PENDING)
            return None
        return lease

    def _replace_action(
        self,
        action: ScheduledTemporalAction,
        state: ScheduledActionState,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        now = self._clock()
        self._actions[action.schedule_id] = ScheduledTemporalAction(
            schedule_id=action.schedule_id,
            tenant_id=action.tenant_id,
            action=action.action,
            execute_at=action.execute_at,
            state=state,
            handler_name=action.handler_name,
            created_at=action.created_at,
            updated_at=now,
            metadata=metadata if metadata is not None else action.metadata,
        )

    def _record(
        self,
        action: ScheduledTemporalAction,
        verdict: ScheduleDecisionVerdict,
        reason: str,
        evaluated_at: str,
        worker_id: str,
        *,
        temporal_decision_id: str = "",
        temporal_verdict: str = "",
    ) -> TemporalRunReceipt:
        receipt = TemporalRunReceipt(
            receipt_id=stable_identifier(
                "temp-run",
                {
                    "schedule_id": action.schedule_id,
                    "verdict": verdict.value,
                    "reason": reason,
                    "at": evaluated_at,
                    "worker_id": worker_id,
                    "count": str(len(self._receipts) + 1),
                },
            ),
            schedule_id=action.schedule_id,
            tenant_id=action.tenant_id,
            verdict=verdict,
            reason=reason,
            evaluated_at=evaluated_at,
            worker_id=worker_id,
            temporal_decision_id=temporal_decision_id,
            temporal_verdict=temporal_verdict,
        )
        self._receipts.append(receipt)
        return receipt

    def _record_temporal(
        self,
        action: ScheduledTemporalAction,
        decision: TemporalActionDecision,
        verdict: ScheduleDecisionVerdict,
        reason: str,
        evaluated_at: str,
        worker_id: str,
    ) -> TemporalRunReceipt:
        return self._record(
            action,
            verdict,
            reason,
            evaluated_at,
            worker_id,
            temporal_decision_id=decision.decision_id,
            temporal_verdict=decision.verdict.value,
        )
