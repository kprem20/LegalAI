from __future__ import annotations

from pathlib import Path

from ai.dataset.adapter import (
    available_years,
    iter_dataset_files,
    load_json_chunks,
    normalize_record,
)
from backend.config.settings import PROJECT_ROOT, settings


def test_dataset_directory_exists():
    assert settings.dataset_path.exists()
    assert settings.dataset_path.is_dir()


def test_dataset_years_cover_expected_range():
    years = available_years()
    assert 1950 in years
    assert 2025 in years
    assert years[0] == 1950


def test_sample_records_have_expected_fields():
    files = list(iter_dataset_files(max_files=3))
    assert files
    required = {
        "chunk_id",
        "case_name",
        "court",
        "judges",
        "date",
        "citation",
        "case_number",
        "ipc",
        "articles",
        "metadata",
        "text",
    }
    for path in files:
        rows = load_json_chunks(path)
        assert isinstance(rows, list)
        assert rows, f"empty file {path}"
        assert required.issubset(rows[0].keys())
        chunk = normalize_record(rows[0], year_folder=path.parent.name, file_path=path)
        assert chunk is not None
        assert chunk.text
        assert chunk.case_id.startswith(path.parent.name)
        assert chunk.chunk_uid


def test_max_files_is_split_across_years(tmp_path: Path):
    for year in ("2000", "2024", "2025"):
        folder = tmp_path / year
        folder.mkdir()
        for i in range(10):
            (folder / f"case_{i}.json").write_text("[]", encoding="utf-8")
    paths = list(iter_dataset_files(tmp_path, years=["2000", "2024", "2025"], max_files=6))
    assert len(paths) == 6
    by_year = {}
    for path in paths:
        by_year.setdefault(path.parent.name, 0)
        by_year[path.parent.name] += 1
    assert by_year == {"2000": 2, "2024": 2, "2025": 2}

    fake = tmp_path / "1950"
    fake.mkdir()
    path = fake / "empty.json"
    path.write_text("[]", encoding="utf-8")
    chunk = normalize_record(
        {"chunk_id": 1, "case_name": "x", "text": "   "},
        year_folder="1950",
        file_path=path,
    )
    assert chunk is None


def test_filename_date_is_recovered_when_date_unknown():
    path = PROJECT_ROOT / "dataset" / "2000" / "V_P_Ahuja_vs_State_Of_Punjab_Ors_on_6_March_2000_1.json"
    if not path.exists():
        return
    rows = load_json_chunks(path)
    chunk = normalize_record(rows[0], year_folder="2000", file_path=path)
    assert chunk is not None
    assert "2000" in chunk.date or chunk.year == 2000
    assert "Ahuja" in chunk.case_name
