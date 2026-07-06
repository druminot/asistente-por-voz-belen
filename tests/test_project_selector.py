"""Tests del selector de proyecto."""

from pathlib import Path

from belen.project_selector import ProjectSelector


def test_parse_proyecto_directo():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("andá al proyecto estimacion") == "estimacion"
    assert sel.parse_command("cambiá a proyecto Casa Rodante") == "Casa Rodante"
    assert sel.parse_command("abrí proyecto smart-home-tablet") == "smart-home-tablet"


def test_parse_no_es_comando():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("creá un archivo main.py") is None
    assert sel.parse_command("explicame cómo funciona esto") is None


def test_normalize():
    assert ProjectSelector._normalize("Estimación") == "estimacion"
    assert ProjectSelector._normalize("Casa Rodante") == "casa rodante"
    assert ProjectSelector._normalize("  Año  ") == "ano"


def test_find_project_exact(tmp_path):
    (tmp_path / "estimacion-de-temperatura-hogar").mkdir()
    (tmp_path / "smart-home-tablet").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.find_project("estimacion-de-temperatura-hogar")
    assert result is not None
    assert result.name == "estimacion-de-temperatura-hogar"


def test_find_project_fuzzy(tmp_path):
    (tmp_path / "estimacion-de-temperatura-hogar").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.find_project("estimacion")
    assert result is not None
    assert "estimacion" in result.name


def test_select_pipeline(tmp_path):
    (tmp_path / "smart-home-tablet").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.select("andá al proyecto smart-home-tablet")
    assert result is not None
    assert result.name == "smart-home-tablet"