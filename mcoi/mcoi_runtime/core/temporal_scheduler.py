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


def _require_trimmed_temporal_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty text")
    if value.strip() != value:
        raise RuntimeCoreInvariantError(f"{field_name} must be trimmed text")
    return value


def _optional_trimmed_temporal_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise RuntimeCoreInvariantError(f"{field_name} must be text")
    if value and value.strip() != value:
        raise RuntimeCoreInvariantError(f"{field_name} must be trimmed text")
    return value


def _resolve_relative_phrase(now: datetime, amount: int, unit: str) -> tuple[str, str]:
    minute_units = {
        "minute",
        "minutes",
        "minuut",
        "minuten",
        "minut",
        "minuter",
        "minutos",
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
        "minit",
        "phut",
        "minuto",
        "minutu",
        "minuta",
        "minuti",
        "lepto",
        "lepta",
        "minutit",
        "noimead",
        "noimeid",
        "munud",
        "munudau",
        "mionaid",
        "mionaidean",
        "minuta",
        "minuti",
        "minutur",
        "minutt",
        "minutten",
        "minutura",
        "minuts",
        "minutoj",
        "minutum",
        "minutas",
        "munut",
        "munutenn",
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
        "gio",
        "oras",
        "saa",
        "ure",
        "sat",
        "sata",
        "uro",
        "uri",
        "chas",
        "chasa",
        "oresh",
        "ores",
        "tund",
        "tundi",
        "valanda",
        "valandas",
        "valandu",
        "uair",
        "uaire",
        "awr",
        "oriau",
        "uairean",
        "klukkustund",
        "klukkustundir",
        "siegha",
        "sieghat",
        "stonn",
        "stonnen",
        "ordura",
        "hora",
        "hores",
        "horas",
        "horo",
        "horoj",
        "eur",
        "eurvezh",
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
        "ngay",
        "araw",
        "siku",
        "dae",
        "dan",
        "dana",
        "dni",
        "dena",
        "denovi",
        "dite",
        "ditesh",
        "mera",
        "meres",
        "paev",
        "paeva",
        "diena",
        "dienu",
        "la",
        "laethanta",
        "diwrnod",
        "diwrnodau",
        "latha",
        "laithean",
        "dag",
        "daga",
        "deeg",
        "jum",
        "jiem",
        "egunera",
        "dia",
        "dies",
        "dias",
        "tago",
        "tagoj",
        "diem",
        "jorn",
        "jorns",
        "deiz",
        "deiziou",
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


def _malay_weekdays() -> dict[str, int]:
    return {
        "isnin": 0,
        "selasa": 1,
        "rabu": 2,
        "khamis": 3,
        "jumaat": 4,
        "sabtu": 5,
        "ahad": 6,
    }


def _vietnamese_weekdays() -> dict[str, int]:
    return {
        "thu hai": 0,
        "thu ba": 1,
        "thu tu": 2,
        "thu nam": 3,
        "thu sau": 4,
        "thu bay": 5,
        "chu nhat": 6,
    }


def _filipino_weekdays() -> dict[str, int]:
    return {
        "lunes": 0,
        "martes": 1,
        "miyerkules": 2,
        "huwebes": 3,
        "biyernes": 4,
        "sabado": 5,
        "linggo": 6,
    }


def _swahili_weekdays() -> dict[str, int]:
    return {
        "jumatatu": 0,
        "jumanne": 1,
        "jumatano": 2,
        "alhamisi": 3,
        "ijumaa": 4,
        "jumamosi": 5,
        "jumapili": 6,
    }


def _afrikaans_weekdays() -> dict[str, int]:
    return {
        "maandag": 0,
        "dinsdag": 1,
        "woensdag": 2,
        "donderdag": 3,
        "vrydag": 4,
        "saterdag": 5,
        "sondag": 6,
    }


def _croatian_weekdays() -> dict[str, int]:
    return {
        "ponedjeljak": 0,
        "utorak": 1,
        "srijeda": 2,
        "cetvrtak": 3,
        "petak": 4,
        "subota": 5,
        "nedjelja": 6,
    }


def _slovenian_weekdays() -> dict[str, int]:
    return {
        "ponedeljek": 0,
        "torek": 1,
        "sreda": 2,
        "cetrtek": 3,
        "petek": 4,
        "sobota": 5,
        "nedelja": 6,
    }


def _serbian_weekdays() -> dict[str, int]:
    return {
        "ponedeljak": 0,
        "utorak": 1,
        "sreda": 2,
        "cetvrtak": 3,
        "petak": 4,
        "subota": 5,
        "nedelja": 6,
    }


def _bulgarian_weekdays() -> dict[str, int]:
    return {
        "ponedelnik": 0,
        "vtornik": 1,
        "sryada": 2,
        "chetvartak": 3,
        "petak": 4,
        "sabota": 5,
        "nedelya": 6,
    }


def _bosnian_weekdays() -> dict[str, int]:
    return {
        "ponedjeljak": 0,
        "utorak": 1,
        "srijeda": 2,
        "cetvrtak": 3,
        "petak": 4,
        "subota": 5,
        "nedjelja": 6,
    }


def _macedonian_weekdays() -> dict[str, int]:
    return {
        "ponedelnik": 0,
        "vtornik": 1,
        "sreda": 2,
        "chetvrtok": 3,
        "petok": 4,
        "sabota": 5,
        "nedela": 6,
    }


def _albanian_weekdays() -> dict[str, int]:
    return {
        "te henen": 0,
        "te marten": 1,
        "te merkuren": 2,
        "te enjten": 3,
        "te premten": 4,
        "te shtunen": 5,
        "te dielen": 6,
    }


def _greek_weekdays() -> dict[str, int]:
    return {
        "deftera": 0,
        "triti": 1,
        "tetarti": 2,
        "pempti": 3,
        "paraskevi": 4,
        "savvato": 5,
        "kyriaki": 6,
    }


def _estonian_weekdays() -> dict[str, int]:
    return {
        "esmaspaeval": 0,
        "teisipaeval": 1,
        "kolmapaeval": 2,
        "neljapaeval": 3,
        "reedel": 4,
        "laupaeval": 5,
        "puhapaeval": 6,
    }


def _lithuanian_weekdays() -> dict[str, int]:
    return {
        "pirmadieni": 0,
        "antradieni": 1,
        "treciadieni": 2,
        "ketvirtadieni": 3,
        "penktadieni": 4,
        "sestadieni": 5,
        "sekmadieni": 6,
    }


def _irish_weekdays() -> dict[str, int]:
    return {
        "luan": 0,
        "mairt": 1,
        "ceadaoin": 2,
        "deardaoin": 3,
        "aoine": 4,
        "satharn": 5,
        "domhnach": 6,
    }


def _welsh_weekdays() -> dict[str, int]:
    return {
        "dydd llun": 0,
        "dydd mawrth": 1,
        "dydd mercher": 2,
        "dydd iau": 3,
        "dydd gwener": 4,
        "dydd sadwrn": 5,
        "dydd sul": 6,
    }


def _scottish_gaelic_weekdays() -> dict[str, int]:
    return {
        "diluain": 0,
        "dimairt": 1,
        "diciadain": 2,
        "diardaoin": 3,
        "dihaoine": 4,
        "disathairne": 5,
        "didomhnaich": 6,
    }


def _icelandic_weekdays() -> dict[str, int]:
    return {
        "manudag": 0,
        "thridjudag": 1,
        "midvikudag": 2,
        "fimmtudag": 3,
        "fostudag": 4,
        "laugardag": 5,
        "sunnudag": 6,
    }


def _maltese_weekdays() -> dict[str, int]:
    return {
        "it-tnejn": 0,
        "it-tlieta": 1,
        "l-erbgha": 2,
        "il-hamis": 3,
        "il-gimgha": 4,
        "is-sibt": 5,
        "il-hadd": 6,
    }


def _luxembourgish_weekdays() -> dict[str, int]:
    return {
        "meindeg": 0,
        "denscheg": 1,
        "mettwoch": 2,
        "donneschdeg": 3,
        "freideg": 4,
        "samschdeg": 5,
        "sonndeg": 6,
    }


def _basque_weekdays() -> dict[str, int]:
    return {
        "astelehena": 0,
        "asteartea": 1,
        "asteazkena": 2,
        "osteguna": 3,
        "ostirala": 4,
        "larunbata": 5,
        "igandea": 6,
    }


def _catalan_weekdays() -> dict[str, int]:
    return {
        "dilluns": 0,
        "dimarts": 1,
        "dimecres": 2,
        "dijous": 3,
        "divendres": 4,
        "dissabte": 5,
        "diumenge": 6,
    }


def _galician_weekdays() -> dict[str, int]:
    return {
        "luns": 0,
        "martes": 1,
        "mercores": 2,
        "xoves": 3,
        "venres": 4,
        "sabado": 5,
        "domingo": 6,
    }


def _esperanto_weekdays() -> dict[str, int]:
    return {
        "lundo": 0,
        "mardo": 1,
        "merkredo": 2,
        "jaudo": 3,
        "vendredo": 4,
        "sabato": 5,
        "dimanco": 6,
    }


def _latin_weekdays() -> dict[str, int]:
    return {
        "lunae": 0,
        "martis": 1,
        "mercurii": 2,
        "iovis": 3,
        "veneris": 4,
        "saturni": 5,
        "solis": 6,
    }


def _interlingua_weekdays() -> dict[str, int]:
    return {
        "lunedi": 0,
        "martedi": 1,
        "mercuridi": 2,
        "jovedi": 3,
        "venerdi": 4,
        "sabbato": 5,
        "dominica": 6,
    }


def _occitan_weekdays() -> dict[str, int]:
    return {
        "diluns": 0,
        "dimars": 1,
        "dimecres": 2,
        "dijous": 3,
        "divendres": 4,
        "dissabte": 5,
        "dimenge": 6,
    }


def _breton_weekdays() -> dict[str, int]:
    return {
        "dilun": 0,
        "dimeurzh": 1,
        "dimercher": 2,
        "diriaou": 3,
        "digwener": 4,
        "disadorn": 5,
        "disul": 6,
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
    if locale_key in {"ms", "ms-my", "ms-bn"}:
        return _resolve_malay_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"vi", "vi-vn"}:
        return _resolve_vietnamese_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"fil", "fil-ph", "tl", "tl-ph"}:
        return _resolve_filipino_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sw", "sw-ke", "sw-tz", "sw-ug"}:
        return _resolve_swahili_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"af", "af-za"}:
        return _resolve_afrikaans_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"hr", "hr-hr"}:
        return _resolve_croatian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sl", "sl-si"}:
        return _resolve_slovenian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sr", "sr-rs", "sr-ba", "sr-latn-rs"}:
        return _resolve_serbian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"bg", "bg-bg"}:
        return _resolve_bulgarian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"bs", "bs-ba"}:
        return _resolve_bosnian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"mk", "mk-mk"}:
        return _resolve_macedonian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"sq", "sq-al", "sq-xk"}:
        return _resolve_albanian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"el", "el-gr", "el-cy"}:
        return _resolve_greek_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"et", "et-ee"}:
        return _resolve_estonian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"lt", "lt-lt"}:
        return _resolve_lithuanian_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"ga", "ga-ie"}:
        return _resolve_irish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"cy", "cy-gb"}:
        return _resolve_welsh_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"gd", "gd-gb"}:
        return _resolve_scottish_gaelic_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"is", "is-is"}:
        return _resolve_icelandic_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"mt", "mt-mt"}:
        return _resolve_maltese_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"lb", "lb-lu"}:
        return _resolve_luxembourgish_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"eu", "eu-es"}:
        return _resolve_basque_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"ca", "ca-es", "ca-ad"}:
        return _resolve_catalan_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"gl", "gl-es"}:
        return _resolve_galician_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"eo", "eo-001"}:
        return _resolve_esperanto_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"la", "la-va"}:
        return _resolve_latin_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"ia", "ia-001"}:
        return _resolve_interlingua_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"oc", "oc-fr", "oc-es"}:
        return _resolve_occitan_temporal_phrase(normalized, now_dt, original_timezone)
    if locale_key in {"br", "br-fr"}:
        return _resolve_breton_temporal_phrase(normalized, now_dt, original_timezone)
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


def _resolve_malay_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"dalam ([1-9][0-9]*) (minit|jam|hari)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hari ini|esok) pukul ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "esok" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(isnin|selasa|rabu|khamis|jumaat|sabtu|ahad) depan pukul ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_malay_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"hari ini", "esok", "malam ini", "nanti", "segera", "minggu depan", "bulan depan", "tahun depan"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"(isnin|selasa|rabu|khamis|jumaat|sabtu|ahad) depan", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_vietnamese_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"sau ([1-9][0-9]*) (phut|gio|ngay)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hom nay|ngay mai) luc ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "ngay mai" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat) tiep theo luc ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_vietnamese_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {"hom nay", "ngay mai", "toi nay", "lat nua", "som", "tuan toi", "thang toi", "nam toi"}:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"(thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat) tiep theo", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_filipino_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"sa loob ng ([1-9][0-9]*) (minuto|oras|araw)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(ngayon|bukas) sa ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "bukas" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"susunod na (lunes|martes|miyerkules|huwebes|biyernes|sabado|linggo) sa ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_filipino_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "ngayon",
        "bukas",
        "mamaya",
        "maya-maya",
        "sa lalong madaling panahon",
        "susunod na linggo",
        "susunod na buwan",
        "susunod na taon",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"susunod na (lunes|martes|miyerkules|huwebes|biyernes|sabado|linggo)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_swahili_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"baada ya ([1-9][0-9]*) (dakika|saa|siku)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(leo|kesho) saa ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "kesho" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(jumatatu|jumanne|jumatano|alhamisi|ijumaa|jumamosi|jumapili) ijayo saa ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_swahili_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "leo",
        "kesho",
        "usiku wa leo",
        "baadaye",
        "hivi karibuni",
        "wiki ijayo",
        "mwezi ujao",
        "mwaka ujao",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"(jumatatu|jumanne|jumatano|alhamisi|ijumaa|jumamosi|jumapili) ijayo", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_afrikaans_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"oor ([1-9][0-9]*) (minuut|minute|uur|ure|dag|dae)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(vandag|more) om ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "more" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"volgende (maandag|dinsdag|woensdag|donderdag|vrydag|saterdag|sondag) om ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_afrikaans_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "vandag",
        "more",
        "vanaand",
        "later",
        "binnekort",
        "volgende week",
        "volgende maand",
        "volgende jaar",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"volgende (maandag|dinsdag|woensdag|donderdag|vrydag|saterdag|sondag)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_croatian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minutu|minute|sat|sata|dan|dana)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(danas|sutra) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "sutra" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"sljedeci (ponedjeljak|utorak|srijeda|cetvrtak|petak|subota|nedjelja) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_croatian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "danas",
        "sutra",
        "veceras",
        "kasnije",
        "uskoro",
        "sljedeci tjedan",
        "sljedeci mjesec",
        "sljedeca godina",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"sljedeci (ponedjeljak|utorak|srijeda|cetvrtak|petak|subota|nedjelja)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_slovenian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"cez ([1-9][0-9]*) (minuto|minuti|uro|uri|dan|dni)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(danes|jutri) ob ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "jutri" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"naslednji (ponedeljek|torek|sreda|cetrtek|petek|sobota|nedelja) ob ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_slovenian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "danes",
        "jutri",
        "nocoj",
        "kasneje",
        "kmalu",
        "naslednji teden",
        "naslednji mesec",
        "naslednje leto",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"naslednji (ponedeljek|torek|sreda|cetrtek|petek|sobota|nedelja)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_serbian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minut|minuta|sat|sata|dan|dana)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(danas|sutra) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "sutra" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"sledeci (ponedeljak|utorak|sreda|cetvrtak|petak|subota|nedelja) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_serbian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "danas",
        "sutra",
        "veceras",
        "kasnije",
        "uskoro",
        "sledece nedelje",
        "sledeci mesec",
        "sledeca godina",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"sledeci (ponedeljak|utorak|sreda|cetvrtak|petak|subota|nedelja)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_bulgarian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"sled ([1-9][0-9]*) (minuta|minuti|chas|chasa|den|dni)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(dnes|utre) v ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "utre" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"sledvasht (ponedelnik|vtornik|sryada|chetvartak|petak|sabota|nedelya) v ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_bulgarian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "dnes",
        "utre",
        "tazi vecher",
        "po-kasno",
        "skoro",
        "sledvashta sedmitsa",
        "sledvasht mesets",
        "sledvashta godina",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"sledvasht (ponedelnik|vtornik|sryada|chetvartak|petak|sabota|nedelya)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_bosnian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minutu|minute|minuta|sat|sata|dan|dana)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(danas|sutra) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "sutra" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"sljedeci (ponedjeljak|utorak|srijeda|cetvrtak|petak|subota|nedjelja) u ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_bosnian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "danas",
        "sutra",
        "veceras",
        "kasnije",
        "uskoro",
        "sljedece sedmice",
        "sljedeci mjesec",
        "sljedeca godina",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"sljedeci (ponedjeljak|utorak|srijeda|cetvrtak|petak|subota|nedjelja)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_macedonian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"za ([1-9][0-9]*) (minuta|minuti|chas|chasa|den|dena|denovi)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(denes|utre) vo ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "utre" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"sleden (ponedelnik|vtornik|sreda|chetvrtok|petok|sabota|nedela) vo ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_macedonian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "denes",
        "utre",
        "vecerva",
        "podocna",
        "naskoro",
        "slednata sedmica",
        "sledniot mesec",
        "slednata godina",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"sleden (ponedelnik|vtornik|sreda|chetvrtok|petok|sabota|nedela)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_albanian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"pas ([1-9][0-9]*) (minute|minuta|ore|oresh|dite|ditesh)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(sot|neser) ne ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "neser" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(te henen|te marten|te merkuren|te enjten|te premten|te shtunen|te dielen) e ardhshme ne ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_albanian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "sot",
        "neser",
        "sonte",
        "me vone",
        "se shpejti",
        "javen e ardhshme",
        "muajin e ardhshem",
        "vitin e ardhshem",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"(te henen|te marten|te merkuren|te enjten|te premten|te shtunen|te dielen) e ardhshme",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_greek_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"se ([1-9][0-9]*) (lepto|lepta|ora|ores|mera|meres)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(simera|avrio) stis ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "avrio" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"tin epomeni (deftera|triti|tetarti|pempti|paraskevi|savvato|kyriaki) stis ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_greek_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "simera",
        "avrio",
        "apopse",
        "argotera",
        "syntoma",
        "tin epomeni evdomada",
        "ton epomeno mina",
        "ton epomeno chrono",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"tin epomeni (deftera|triti|tetarti|pempti|paraskevi|savvato|kyriaki)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_estonian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"([1-9][0-9]*) (minut|minutit|tund|tundi|paev|paeva) parast", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(tana|homme) kell ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "homme" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"jargmisel (esmaspaeval|teisipaeval|kolmapaeval|neljapaeval|reedel|laupaeval|puhapaeval) kell ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_estonian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "tana",
        "homme",
        "tana ohtul",
        "hiljem",
        "varsti",
        "jargmisel nadalal",
        "jargmisel kuul",
        "jargmisel aastal",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"jargmisel (esmaspaeval|teisipaeval|kolmapaeval|neljapaeval|reedel|laupaeval|puhapaeval)",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_lithuanian_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"po ([1-9][0-9]*) (minute|minutes|valanda|valandas|valandu|diena|dienu)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(siandien|rytoj) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "rytoj" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"kita (pirmadieni|antradieni|treciadieni|ketvirtadieni|penktadieni|sestadieni|sekmadieni) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_lithuanian_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "siandien",
        "rytoj",
        "si vakara",
        "veliau",
        "netrukus",
        "kita savaite",
        "kita menesi",
        "kitais metais",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"kita (pirmadieni|antradieni|treciadieni|ketvirtadieni|penktadieni|sestadieni|sekmadieni)",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_irish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"i gceann ([1-9][0-9]*) (noimead|noimeid|uair|uaire|la|laethanta)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(inniu|amarach) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "amarach" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"an chead (luan|mairt|ceadaoin|deardaoin|aoine|satharn|domhnach) eile ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_irish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "inniu",
        "amarach",
        "anocht",
        "nios deanai",
        "go luath",
        "an tseachtain seo chugainn",
        "an mhi seo chugainn",
        "an bhliain seo chugainn",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"an chead (luan|mairt|ceadaoin|deardaoin|aoine|satharn|domhnach) eile", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_welsh_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"mewn ([1-9][0-9]*) (munud|munudau|awr|oriau|diwrnod|diwrnodau)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(heddiw|yfory) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "yfory" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(dydd llun|dydd mawrth|dydd mercher|dydd iau|dydd gwener|dydd sadwrn|dydd sul) nesaf ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_welsh_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "heddiw",
        "yfory",
        "heno",
        "yn nes ymlaen",
        "cyn bo hir",
        "wythnos nesaf",
        "mis nesaf",
        "blwyddyn nesaf",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"(dydd llun|dydd mawrth|dydd mercher|dydd iau|dydd gwener|dydd sadwrn|dydd sul) nesaf",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_scottish_gaelic_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"ann an ([1-9][0-9]*) (mionaid|mionaidean|uair|uairean|latha|laithean)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(an-diugh|a-maireach) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "a-maireach" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"an ath (diluain|dimairt|diciadain|diardaoin|dihaoine|disathairne|didomhnaich) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_scottish_gaelic_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "an-diugh",
        "a-maireach",
        "a-nochd",
        "nas fhaide air adhart",
        "a dh aithghearr",
        "an ath sheachdain",
        "an ath mhios",
        "an ath bhliadhna",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"an ath (diluain|dimairt|diciadain|diardaoin|dihaoine|disathairne|didomhnaich)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_icelandic_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"eftir ([1-9][0-9]*) (minuta|minutur|klukkustund|klukkustundir|dag|daga)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(i dag|a morgun) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "a morgun" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"naesta (manudag|thridjudag|midvikudag|fimmtudag|fostudag|laugardag|sunnudag) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_icelandic_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "i dag",
        "a morgun",
        "i kvold",
        "seinna",
        "fljotlega",
        "naestu viku",
        "naesta manud",
        "naesta ar",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"naesta (manudag|thridjudag|midvikudag|fimmtudag|fostudag|laugardag|sunnudag)",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_maltese_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"fi ([1-9][0-9]*) (minuta|minuti|siegha|sieghat|jum|jiem)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(illum|ghada) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "ghada" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(it-tnejn|it-tlieta|l-erbgha|il-hamis|il-gimgha|is-sibt|il-hadd) li gej ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_maltese_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "illum",
        "ghada",
        "illejla",
        "aktar tard",
        "dalwaqt",
        "il-gimgha d-diehla",
        "ix-xahar id-diehel",
        "is-sena d-diehla",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"(it-tnejn|it-tlieta|l-erbgha|il-hamis|il-gimgha|is-sibt|il-hadd) li gej",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_luxembourgish_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"an ([1-9][0-9]*) (minutt|minutten|stonn|stonnen|dag|deeg)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(haut|muer) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "muer" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"naechste (meindeg|denscheg|mettwoch|donneschdeg|freideg|samschdeg|sonndeg) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_luxembourgish_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "haut",
        "muer",
        "haut den owend",
        "speider",
        "geschwenn",
        "naechst woch",
        "naechste mount",
        "naechst joer",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"naechste (meindeg|denscheg|mettwoch|donneschdeg|freideg|samschdeg|sonndeg)",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_basque_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"hemendik ([1-9][0-9]*) (minutura|ordura|egunera)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(gaur|bihar) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "bihar" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"hurrengo (astelehena|asteartea|asteazkena|osteguna|ostirala|larunbata|igandea) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_basque_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "gaur",
        "bihar",
        "gaur gauean",
        "geroago",
        "laster",
        "hurrengo astea",
        "hurrengo hilabetea",
        "hurrengo urtea",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"hurrengo (astelehena|asteartea|asteazkena|osteguna|ostirala|larunbata|igandea)",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_catalan_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"en ([1-9][0-9]*) (minut|minuts|hora|hores|dia|dies)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(avui|dema) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "dema" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge) vinent ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_catalan_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "avui",
        "dema",
        "aquest vespre",
        "mes tard",
        "aviat",
        "setmana vinent",
        "mes vinent",
        "any vinent",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(
        r"(dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge) vinent",
        normalized,
    ):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_galician_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"en ([1-9][0-9]*) (minuto|minutos|hora|horas|dia|dias)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hoxe|mana) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "mana" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"proximo (luns|martes|mercores|xoves|venres|sabado|domingo) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_galician_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "hoxe",
        "mana",
        "esta noite",
        "mais tarde",
        "axina",
        "proxima semana",
        "proximo mes",
        "proximo ano",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"proximo (luns|martes|mercores|xoves|venres|sabado|domingo)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_esperanto_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"post ([1-9][0-9]*) (minuto|minutoj|horo|horoj|tago|tagoj)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hodiau|morgau) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "morgau" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"venonta (lundo|mardo|merkredo|jaudo|vendredo|sabato|dimanco) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_esperanto_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "hodiau",
        "morgau",
        "ci-vespere",
        "poste",
        "baldau",
        "venonta semajno",
        "venonta monato",
        "venonta jaro",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"venonta (lundo|mardo|merkredo|jaudo|vendredo|sabato|dimanco)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_latin_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"post ([1-9][0-9]*) (minutum|minuta|hora|horas|diem|dies)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hodie|cras) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "cras" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"proximo (lunae|martis|mercurii|iovis|veneris|saturni|solis) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_latin_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "hodie",
        "cras",
        "hac nocte",
        "postea",
        "mox",
        "proxima septimana",
        "proximus mensis",
        "proximus annus",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"proximo (lunae|martis|mercurii|iovis|veneris|saturni|solis)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_interlingua_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"post ([1-9][0-9]*) (minuta|minutas|hora|horas|die|dies)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hodie|deman) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "deman" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"proxime (lunedi|martedi|mercuridi|jovedi|venerdi|sabbato|dominica) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_interlingua_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "hodie",
        "deman",
        "iste nocte",
        "plus tarde",
        "tosto",
        "proxime septimana",
        "proxime mense",
        "proxime anno",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"proxime (lunedi|martedi|mercuridi|jovedi|venerdi|sabbato|dominica)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_occitan_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"daqui ([1-9][0-9]*) (minuta|minutas|ora|oras|jorn|jorns)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(uei|deman) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "deman" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"prochain (diluns|dimars|dimecres|dijous|divendres|dissabte|dimenge) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_occitan_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "uei",
        "deman",
        "aquesta nuoch",
        "pus tard",
        "leu",
        "prochaine setmana",
        "prochain mes",
        "prochain an",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"prochain (diluns|dimars|dimecres|dijous|divendres|dissabte|dimenge)", normalized):
        return "ambiguous", "temporal_phrase_ambiguous", ""
    return "unsupported", "temporal_phrase_unsupported", ""


def _resolve_breton_temporal_phrase(
    normalized: str,
    now: datetime,
    original_timezone: str,
) -> tuple[str, str, str]:
    relative = re.fullmatch(r"a-benn ([1-9][0-9]*) (munut|munutenn|eur|eurvezh|deiz|deiziou)", normalized)
    if relative is not None:
        resolved, reason = _resolve_relative_phrase(now, int(relative.group(1)), relative.group(2))
        return ("exact" if resolved else "unsupported"), reason, resolved
    wall_time = re.fullmatch(r"(hiziv|warc hoazh) ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)", normalized)
    if wall_time is not None:
        resolved, reason = _resolve_relative_wall_time(
            now,
            original_timezone=original_timezone,
            day_offset=1 if wall_time.group(1) == "warc hoazh" else 0,
            hour=int(wall_time.group(2)),
            minute=int(wall_time.group(3)),
            mode=wall_time.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    next_weekday = re.fullmatch(
        r"(dilun|dimeurzh|dimercher|diriaou|digwener|disadorn|disul) a zeu ([0-9]{1,2}):([0-9]{2}) ?(utc|z|local)",
        normalized,
    )
    if next_weekday is not None:
        resolved, reason = _resolve_next_weekday_wall_time(
            now,
            original_timezone=original_timezone,
            weekday=_breton_weekdays()[next_weekday.group(1)],
            hour=int(next_weekday.group(2)),
            minute=int(next_weekday.group(3)),
            mode=next_weekday.group(4),
        )
        return ("exact" if resolved else "unsupported"), reason, resolved
    if normalized in {
        "hiziv",
        "warc hoazh",
        "fenoz",
        "diwezhatoc",
        "buan",
        "ar sizhun a zeu",
        "ar miz a zeu",
        "ar bloaz a zeu",
    }:
        return "ambiguous", "temporal_phrase_ambiguous", ""
    if re.fullmatch(r"(dilun|dimeurzh|dimercher|diriaou|digwener|disadorn|disul) a zeu", normalized):
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
        schedule_id = _require_trimmed_temporal_text(schedule_id, "schedule_id")
        handler_name = _optional_trimmed_temporal_text(handler_name, "handler_name")
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
        if action.temporal_phrase_policy == "ignore":
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
            _require_trimmed_temporal_text(action.schedule_id, "schedule_id")
            _optional_trimmed_temporal_text(action.handler_name, "handler_name")
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
