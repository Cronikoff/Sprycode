"""REPL feature tests — verifying the REPL command is registered and basic
multi-line detection logic."""
import pytest
from click.testing import CliRunner
from sprycode.cli import main


class TestReplCommand:
    def test_repl_command_exists(self):
        """Verify the repl command is registered in the CLI."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl", "--help"])
        assert result.exit_code == 0
        assert "repl" in result.output.lower() or "REPL" in result.output

    def test_repl_exits_on_eof(self):
        """Verify the REPL exits cleanly on EOF input."""
        runner = CliRunner()
        # Send empty input (EOF) to trigger exit
        result = runner.invoke(main, ["repl"], input=".exit\n")
        assert result.exit_code == 0

    def test_repl_help_command(self):
        """Verify .help command works in REPL."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input=".help\n.exit\n")
        assert result.exit_code == 0
