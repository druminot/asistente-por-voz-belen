"""Tests del selector de proyecto."""

from pathlib import Path

from belen.project_selector import ProjectMatch, ProjectSelector


def test_parse_proyecto_directo():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("andá al proyecto estimacion") == "estimacion"
    assert sel.parse_command("cambiá a proyecto Casa Rodante") == "Casa Rodante"
    assert sel.parse_command("abrí proyecto smart-home-tablet") == "smart-home-tablet"


def test_parse_proyecto_sin_palabra_proyecto():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("andá al medidor") == "medidor"
    assert sel.parse_command("abrí belen") == "belen"


def test_parse_no_es_comando():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("creá un archivo main.py") is None
    assert sel.parse_command("explicame cómo funciona esto") is None
    assert sel.parse_command("hola") is None
    assert sel.parse_command("") is None


def test_parse_limpia_puntuacion():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.parse_command("andá al proyecto foo, por favor") == "foo"


def test_normalize():
    from belen.project_selector import _normalize

    assert _normalize("Estimación") == "estimacion"
    assert _normalize("Casa Rodante") == "casa rodante"
    assert _normalize("  Año  ") == "ano"
    assert _normalize("Niño") == "nino"


def test_find_project_exact(tmp_path):
    (tmp_path / "estimacion-de-temperatura-hogar").mkdir()
    (tmp_path / "smart-home-tablet").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.find_project("estimacion-de-temperatura-hogar")
    assert isinstance(result, ProjectMatch)
    assert result.path.name == "estimacion-de-temperatura-hogar"
    assert result.score == 1.0


def test_find_project_fuzzy(tmp_path):
    (tmp_path / "estimacion-de-temperatura-hogar").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.find_project("estimacion")
    assert result is not None
    assert "estimacion" in result.path.name


def test_find_project_acentos(tmp_path):
    (tmp_path / "estimacion-de-temperatura-hogar").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.find_project("Estimación")
    assert result is not None
    assert result.path.name == "estimacion-de-temperatura-hogar"


def test_find_project_no_existe(tmp_path):
    (tmp_path / "foo").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)
    assert sel.find_project("proyecto-inexistente-xyz") is None


def test_find_project_empty_name():
    sel = ProjectSelector(projects_dir=Path("/tmp"))
    assert sel.find_project("") is None
    assert sel.find_project(None) is None  # type: ignore[arg-type]


def test_select_pipeline(tmp_path):
    (tmp_path / "smart-home-tablet").mkdir()
    sel = ProjectSelector(projects_dir=tmp_path)

    result = sel.select("andá al proyecto smart-home-tablet")
    assert result is not None
    assert result.path.name == "smart-home-tablet"


def test_select_no_projects_dir(tmp_path):
    """Si el dir no existe, devuelve None limpio."""
    sel = ProjectSelector(projects_dir=tmp_path / "no-existe")
    assert sel.select("andá al proyecto foo") is None


def test_list_projects_ignora_ocultos(tmp_path):
    (tmp_path / "visible").mkdir()
    (tmp_path / ".oculto").mkdir()
    (tmp_path / "archivo.txt").touch()

    sel = ProjectSelector(projects_dir=tmp_path)
    projects = sel.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "visible"
