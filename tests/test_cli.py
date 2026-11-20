import pytest

from company_core_validator.cli import main


@pytest.mark.parametrize("flag", ["--dry-run", "--apply"])
def test_write_suppressing_flags_do_not_exist(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", flag])
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
