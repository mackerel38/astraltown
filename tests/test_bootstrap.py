import sys

import pytest

from astral_town.data.loader import load_builtin, load_file, loads


def test_import_and_builtin():
    assert load_builtin()["rules"]["board_size"]["value"] == 16
    assert not any(name.startswith("PySide6") for name in sys.modules)


@pytest.mark.parametrize("suffix,text", [(".json", '{"answer": 16}'), (".yaml", "answer: 16")])
def test_load_file(tmp_path, suffix, text):
    path = tmp_path / ("config" + suffix)
    path.write_text(text)
    assert load_file(path) == {"answer": 16}


def test_reject_non_mapping():
    with pytest.raises(ValueError):
        loads("[]", ".json")


def test_yaml_does_not_execute():
    import yaml
    with pytest.raises(yaml.YAMLError):
        loads("!!python/object/apply:os.system ['false']", ".yaml")
