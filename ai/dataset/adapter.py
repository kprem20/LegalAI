from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from backend.config.settings import UNAVAILABLE, settings

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

FILENAME_DATE_RE = re.compile(
    r"_on_(\d{1,2})_([A-Za-z]+)_(\d{4})",
    re.IGNORECASE,
)
TEXT_DATE_RE = re.compile(
    r"DATE OF JUDGMENT:\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
    re.IGNORECASE,
)


def display_or_unavailable(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, list):
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(cleaned) if cleaned else UNAVAILABLE
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "none", "null", "n/a", "na"}:
        return UNAVAILABLE
    return text


def parse_filename_date(stem: str) -> tuple[Optional[str], Optional[int]]:
    match = FILENAME_DATE_RE.search(stem)
    if not match:
        return None, None
    day, month_name, year_s = match.groups()
    month = MONTHS.get(month_name.lower())
    year = int(year_s)
    if not month:
        return f"{day} {month_name} {year}", year
    return f"{int(day):02d} {month_name.title()} {year}", year


def join_list(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def normalize_court(court: str) -> str:
    text = (court or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "supreme court" in lowered:
        return "Supreme Court of India"
    return text


def make_case_id(year: str, file_stem: str) -> str:
    return f"{year}::{file_stem}"


def make_chunk_uid(case_id: str, chunk_id: Any) -> str:
    return f"{case_id}::{chunk_id}"


@dataclass
class NormalizedChunk:
    chunk_uid: str
    case_id: str
    chunk_id: int
    case_name: str
    citation: str
    date: str
    court: str
    year: Optional[int]
    judges: str
    case_number: str
    ipc: str
    articles: str
    text: str
    source_file: str
    file_name: str
    raw: dict[str, Any] = field(repr=False)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_record(
    record: dict[str, Any],
    *,
    year_folder: str,
    file_path: Path,
) -> Optional[NormalizedChunk]:
    text = str(record.get("text") or "").strip()
    if not text:
        return None

    file_stem = file_path.stem
    case_id = make_case_id(year_folder, file_stem)
    chunk_id = _safe_int(record.get("chunk_id"), 0)
    chunk_uid = make_chunk_uid(case_id, chunk_id)

    parsed_date, parsed_year = parse_filename_date(file_stem)
    meta = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    meta_year = meta.get("year")
    year: Optional[int] = None
    if isinstance(meta_year, int):
        year = meta_year
    elif year_folder.isdigit():
        year = int(year_folder)
    if parsed_year:
        year = parsed_year

    date_field = display_or_unavailable(record.get("date"))
    if date_field == UNAVAILABLE:
        if parsed_date:
            date_field = parsed_date
        else:
            text_match = TEXT_DATE_RE.search(text)
            if text_match:
                d, m, y = text_match.groups()
                date_field = f"{int(d):02d}/{int(m):02d}/{y}"
                year = int(y)

    citation = display_or_unavailable(record.get("citation"))
    judges = join_list(record.get("judges"))
    court = normalize_court(str(record.get("court") or ""))
    if not court:
        court = UNAVAILABLE

    return NormalizedChunk(
        chunk_uid=chunk_uid,
        case_id=case_id,
        chunk_id=chunk_id,
        case_name=str(record.get("case_name") or file_stem.replace("_", " ")).strip(),
        citation=citation,
        date=date_field,
        court=court,
        year=year,
        judges=judges,
        case_number=display_or_unavailable(record.get("case_number")),
        ipc=join_list(record.get("ipc")),
        articles=join_list(record.get("articles")),
        text=text,
        source_file=str(file_path.relative_to(settings.dataset_path.parent)
                        if settings.dataset_path.parent in file_path.parents
                        else file_path),
        file_name=str(meta.get("file_name") or file_path.name),
        raw=record,
    )


def iter_dataset_files(
    dataset_dir: Optional[Path] = None,
    years: Optional[list[str]] = None,
    max_files: Optional[int] = None,
) -> Iterator[Path]:
    """Yield judgment JSON paths.

    When ``max_files`` is set across multiple year folders, the budget is
    split evenly so one early year cannot consume the entire limit.
    """
    root = dataset_dir or settings.dataset_path
    if not root.exists():
        return
    year_dirs = sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda p: p.name,
    )
    if years:
        wanted = {str(y) for y in years}
        year_dirs = [p for p in year_dirs if p.name in wanted]
    if not year_dirs:
        return

    per_year_files = [sorted(year_dir.glob("*.json")) for year_dir in year_dirs]
    if max_files is None:
        for files in per_year_files:
            yield from files
        return

    n_years = len(per_year_files)
    base = max_files // n_years
    remainder = max_files % n_years
    emitted = 0
    for index, files in enumerate(per_year_files):
        allotment = base + (1 if index < remainder else 0)
        for path in files[:allotment]:
            yield path
            emitted += 1
            if emitted >= max_files:
                return


def load_json_chunks(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def iter_normalized_chunks(
    dataset_dir: Optional[Path] = None,
    years: Optional[list[str]] = None,
    max_files: Optional[int] = None,
) -> Iterator[NormalizedChunk]:
    for path in iter_dataset_files(dataset_dir, years=years, max_files=max_files):
        year_folder = path.parent.name
        for record in load_json_chunks(path):
            chunk = normalize_record(record, year_folder=year_folder, file_path=path)
            if chunk:
                yield chunk


def load_case_chunks(case_id: str, dataset_dir: Optional[Path] = None) -> list[NormalizedChunk]:
    if "::" not in case_id:
        return []
    year, stem = case_id.split("::", 1)
    root = dataset_dir or settings.dataset_path
    path = root / year / f"{stem}.json"
    if not path.exists():
        return []
    chunks: list[NormalizedChunk] = []
    for record in load_json_chunks(path):
        chunk = normalize_record(record, year_folder=year, file_path=path)
        if chunk:
            chunks.append(chunk)
    chunks.sort(key=lambda c: c.chunk_id)
    return chunks


def dataset_file_count(dataset_dir: Optional[Path] = None) -> int:
    root = dataset_dir or settings.dataset_path
    if not root.exists():
        return 0
    return sum(1 for _ in iter_dataset_files(root))


def available_years(dataset_dir: Optional[Path] = None) -> list[int]:
    root = dataset_dir or settings.dataset_path
    if not root.exists():
        return []
    years = []
    for path in root.iterdir():
        if path.is_dir() and path.name.isdigit():
            years.append(int(path.name))
    return sorted(years)
