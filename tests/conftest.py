import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EFT_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"
