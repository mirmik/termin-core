from pathlib import Path

from termin_build import relocated_sdk_smoke


def test_relocated_sdk_smoke_rejects_missing_sdk(tmp_path, capsys):
    result = relocated_sdk_smoke.relocated_sdk_smoke(tmp_path / "missing")

    assert result == 1
    assert "SDK root does not exist" in capsys.readouterr().err


def test_relocated_sdk_smoke_copies_before_verification(tmp_path, monkeypatch):
    source = tmp_path / "source-sdk"
    destination = tmp_path / "relocated-sdk"
    source.mkdir()
    (source / "marker").write_text("sdk", encoding="utf-8")
    verified = []

    def verify(path: Path) -> int:
        verified.append(path)
        assert (path / "marker").read_text(encoding="utf-8") == "sdk"
        return 0

    monkeypatch.setattr(relocated_sdk_smoke, "verify_relocated_sdk", verify)

    result = relocated_sdk_smoke.relocated_sdk_smoke(
        source,
        destination_root=destination,
    )

    assert result == 0
    assert verified == [destination.resolve()]


def test_relocated_sdk_smoke_refuses_existing_destination(tmp_path, capsys):
    source = tmp_path / "source-sdk"
    destination = tmp_path / "existing"
    source.mkdir()
    destination.mkdir()

    result = relocated_sdk_smoke.relocated_sdk_smoke(
        source,
        destination_root=destination,
    )

    assert result == 1
    assert "destination already exists" in capsys.readouterr().err
