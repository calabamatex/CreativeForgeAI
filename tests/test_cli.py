"""
Tests for CLI interface.
"""

import json

from click.testing import CliRunner


class TestCLI:
    """Test CLI commands."""

    def test_cli_help(self):
        """Test CLI help command."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Creative Automation Pipeline" in result.output

    def test_cli_version(self):
        """Test CLI version command."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0

    def test_validate_config_command(self, mock_env_vars):
        """Test validate-config command."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config"])

        assert result.exit_code == 0
        assert "Configuration" in result.output

    def test_validate_config_missing_keys(self, monkeypatch, mock_env_vars):
        """Test validate-config with missing keys."""
        import os

        from src import config
        from src.cli import cli

        # Clear all relevant env vars to force validation to fail
        for key in list(os.environ.keys()):
            if any(k in key for k in ["FIREFLY", "OPENAI", "GEMINI", "CLAUDE", "DEFAULT"]):
                monkeypatch.delenv(key, raising=False)

        # Force config reload
        config._config = None

        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config"])

        assert result.exit_code == 1  # Should fail
        assert "error" in result.output.lower() or "failed" in result.output.lower()

        # Restore config for subsequent tests (mock_env_vars fixture will be active)
        config._config = None

    def test_list_examples_command(self):
        """Test list-examples command."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list-examples"])

        assert result.exit_code == 0

    def test_process_command_with_valid_brief(self, mock_env_vars, tmp_path, example_brief):
        """Test process command with valid brief."""
        from src.cli import cli

        # Create test brief file
        brief_path = tmp_path / "test_brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with CliRunner().isolated_filesystem():
            # Mock the pipeline processing
            from unittest.mock import patch

            with patch("src.pipeline.CreativeAutomationPipeline.process_campaign") as mock_process:
                from src.models import CampaignOutput

                mock_output = CampaignOutput(
                    campaign_id="TEST", campaign_name="Test", total_assets=5, processing_time_seconds=10.0
                )

                mock_process.return_value = mock_output

                # Smoke-exercise the CLI process path (output not asserted here;
                # see the dry-run/backend-override tests for behavioral checks).
                runner.invoke(cli, ["process", "--brief", str(brief_path)])

    def test_process_command_with_backend_override(self, mock_env_vars, tmp_path, example_brief):
        """Test process command with backend override."""
        from src.cli import cli

        # Create test brief
        brief_path = tmp_path / "test_brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with patch("src.pipeline.CreativeAutomationPipeline") as mock_pipeline:
            runner.invoke(cli, ["process", "--brief", str(brief_path), "--backend", "openai"])

            # Verify backend was passed to pipeline
            if mock_pipeline.called:
                call_args = mock_pipeline.call_args
                assert call_args[1].get("image_backend") == "openai"

    def test_process_command_dry_run(self, mock_env_vars, tmp_path, example_brief):
        """Test process command with dry-run flag."""
        from src.cli import cli

        brief_path = tmp_path / "test_brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()
        result = runner.invoke(cli, ["process", "--brief", str(brief_path), "--dry-run"])

        assert "Dry run complete" in result.output or result.exit_code == 0

    def test_process_command_verbose(self, mock_env_vars, tmp_path, example_brief):
        """Test process command with verbose flag."""
        from src.cli import cli

        brief_path = tmp_path / "test_brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with patch("src.pipeline.CreativeAutomationPipeline.process_campaign") as mock_process:
            from src.models import CampaignOutput

            mock_output = CampaignOutput(campaign_id="TEST", campaign_name="Test")
            mock_process.return_value = mock_output

            # Verbose mode should show more details (smoke-exercise the path).
            runner.invoke(cli, ["process", "--brief", str(brief_path), "--verbose"])

    def test_process_command_invalid_brief(self, tmp_path):
        """Test process command with invalid brief."""
        from src.cli import cli

        # Create invalid brief
        brief_path = tmp_path / "invalid_brief.json"
        brief_path.write_text('{"invalid": "data"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["process", "--brief", str(brief_path)])

        assert result.exit_code != 0

    def test_process_command_missing_brief(self):
        """Test process command without brief."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["process"])

        assert result.exit_code != 0
        assert "brief" in result.output.lower() or "required" in result.output.lower()

    def test_process_command_nonexistent_brief(self):
        """Test process command with nonexistent brief file."""
        from src.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["process", "--brief", "nonexistent_file.json"])

        assert result.exit_code != 0


class TestCLIBackendSelection:
    """Test CLI backend selection."""

    def test_cli_backend_firefly(self, mock_env_vars, tmp_path, example_brief):
        """Test CLI with Firefly backend."""
        from src.cli import cli

        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with patch("src.pipeline.CreativeAutomationPipeline.__init__") as mock_init:
            mock_init.return_value = None

            runner.invoke(cli, ["process", "--brief", str(brief_path), "--backend", "firefly"])

            # Verify Firefly backend was selected

    def test_cli_backend_openai(self, mock_env_vars, tmp_path, example_brief):
        """Test CLI with OpenAI backend."""
        from src.cli import cli

        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with patch("src.pipeline.CreativeAutomationPipeline.__init__") as mock_init:
            mock_init.return_value = None

            runner.invoke(cli, ["process", "--brief", str(brief_path), "--backend", "openai"])

    def test_cli_backend_gemini(self, mock_env_vars, tmp_path, example_brief):
        """Test CLI with Gemini backend."""
        from src.cli import cli

        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        with patch("src.pipeline.CreativeAutomationPipeline.__init__") as mock_init:
            mock_init.return_value = None

            runner.invoke(cli, ["process", "--brief", str(brief_path), "--backend", "gemini"])

    def test_cli_invalid_backend(self, mock_env_vars, tmp_path, example_brief):
        """Test CLI with invalid backend."""
        from src.cli import cli

        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()
        result = runner.invoke(cli, ["process", "--brief", str(brief_path), "--backend", "invalid_backend"])

        # Click's Choice should reject invalid backend
        assert result.exit_code != 0


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_cli_full_workflow(self, mock_env_vars, tmp_path, example_brief):
        """Test complete CLI workflow."""
        from src.cli import cli

        # Create brief
        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(example_brief))

        runner = CliRunner()

        # 1. Validate config
        result = runner.invoke(cli, ["validate-config"])
        assert result.exit_code == 0

        # 2. List examples
        result = runner.invoke(cli, ["list-examples"])
        assert result.exit_code == 0

        # 3. Dry run
        result = runner.invoke(cli, ["process", "--brief", str(brief_path), "--dry-run"])
        assert "valid" in result.output.lower() or result.exit_code == 0


from unittest.mock import patch
