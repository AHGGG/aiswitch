"""Extended tests for preset.py module to improve coverage."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from aiswitch.preset import PresetManager
from aiswitch.config import PresetConfig, ProjectConfig


class TestPresetManagerExtended:
    def setup_method(self):
        self.preset_manager = PresetManager()

    def test_add_preset_flexible_success(self, temp_config_dir):
        """Test adding preset with flexible variables."""
        variables = {
            "API_KEY": "test-key",
            "API_URL": "https://api.test.com",
            "CUSTOM_VAR": "custom-value"
        }

        preset = self.preset_manager.add_preset_flexible(
            name="test-preset",
            variables=variables,
            description="Test preset",
            tags=["test", "api"]
        )

        assert preset.name == "test-preset"
        assert preset.description == "Test preset"
        assert preset.tags == ["test", "api"]
        assert preset.variables == variables

    def test_add_preset_flexible_already_exists(self, temp_config_dir):
        """Test adding preset when it already exists."""
        variables = {"API_KEY": "test"}
        self.preset_manager.add_preset_flexible("existing", variables)

        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.add_preset_flexible("existing", variables)
        assert "already exists" in str(exc_info.value)

    def test_add_preset_flexible_empty_variables(self, temp_config_dir):
        """Test adding preset with empty variables."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.add_preset_flexible("test", {})
        assert "At least one environment variable" in str(exc_info.value)

    def test_add_preset_flexible_invalid_variables(self, temp_config_dir):
        """Test adding preset with invalid variables."""
        with patch.object(self.preset_manager.env_manager, 'validate_env_variables') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid variable")

            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.add_preset_flexible("test", {"KEY": "value"})
            assert "Invalid configuration" in str(exc_info.value)

    def test_add_preset_with_model(self, temp_config_dir):
        """Test adding regular preset with model."""
        preset = self.preset_manager.add_preset(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com",
            model="gpt-4",
            description="OpenAI preset",
            tags=["openai", "gpt"]
        )

        assert preset.variables["API_MODEL"] == "gpt-4"
        assert preset.description == "OpenAI preset"
        assert preset.tags == ["openai", "gpt"]

    def test_add_preset_without_model(self, temp_config_dir):
        """Test adding regular preset without model."""
        preset = self.preset_manager.add_preset(
            name="api",
            api_key="key",
            base_url="https://api.com"
        )

        assert "API_MODEL" not in preset.variables
        assert preset.description == ""
        assert preset.tags == []

    def test_remove_preset_current_preset(self, temp_config_dir):
        """Test removing the currently active preset."""
        # Add and set current preset
        self.preset_manager.add_preset("test", "key", "url")
        self.preset_manager.use_preset("test")

        # Remove it
        result = self.preset_manager.remove_preset("test")

        assert result is True
        assert self.preset_manager.get_current_preset() is None

    def test_remove_preset_not_current(self, temp_config_dir):
        """Test removing a preset that is not current."""
        self.preset_manager.add_preset("test1", "key1", "url1")
        self.preset_manager.add_preset("test2", "key2", "url2")
        self.preset_manager.use_preset("test1")

        result = self.preset_manager.remove_preset("test2")

        assert result is True
        current = self.preset_manager.get_current_preset()
        assert current.name == "test1"

    def test_remove_preset_nonexistent(self, temp_config_dir):
        """Test removing a preset that doesn't exist."""
        result = self.preset_manager.remove_preset("nonexistent")
        assert result is False

    def test_use_preset_similar_names(self, temp_config_dir):
        """Test using preset with similar names suggestion."""
        self.preset_manager.add_preset("openai", "key", "url")
        self.preset_manager.add_preset("openai-test", "key2", "url2")

        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.use_preset("opena")
        assert "Did you mean" in str(exc_info.value)

    def test_use_preset_no_similar_names(self, temp_config_dir):
        """Test using preset with no similar names."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.use_preset("nonexistent")
        assert "Use 'aiswitch list'" in str(exc_info.value)

    def test_use_preset_without_apply_to_env(self, temp_config_dir):
        """Test using preset without applying to environment."""
        self.preset_manager.add_preset("test", "key", "url")

        preset, applied_vars, cleared_vars = self.preset_manager.use_preset("test", apply_to_env=False)

        assert preset.name == "test"
        assert applied_vars == {}
        assert cleared_vars == []

    def test_clear_current_with_preset(self, temp_config_dir):
        """Test clearing current preset when one exists."""
        self.preset_manager.add_preset("test", "key", "url")
        self.preset_manager.use_preset("test")

        with patch.object(self.preset_manager.env_manager, 'clear_variables', return_value=["API_KEY"]) as mock_clear:
            cleared_vars = self.preset_manager.clear_current()

        assert cleared_vars == ["API_KEY"]
        assert self.preset_manager.get_current_preset() is None
        mock_clear.assert_called_once_with(["API_KEY", "API_BASE_URL"])

    def test_clear_current_without_preset(self, temp_config_dir):
        """Test clearing current when no preset is set."""
        with patch.object(self.preset_manager.env_manager, 'clear_variables', return_value=[]) as mock_clear:
            cleared_vars = self.preset_manager.clear_current()

        assert cleared_vars == []
        mock_clear.assert_called_once_with()

    def test_save_project_config_with_preset_name(self, temp_config_dir):
        """Test saving project config with explicit preset name."""
        self.preset_manager.add_preset("test", "key", "url")

        project_config = self.preset_manager.save_project_config(
            preset_name="test",
            overrides={"API_MODEL": "custom-model"}
        )

        assert project_config.preset == "test"
        assert project_config.overrides == {"API_MODEL": "custom-model"}

    def test_save_project_config_without_preset_name(self, temp_config_dir):
        """Test saving project config without explicit preset name."""
        self.preset_manager.add_preset("current", "key", "url")
        self.preset_manager.use_preset("current")

        project_config = self.preset_manager.save_project_config()

        assert project_config.preset == "current"

    def test_save_project_config_no_current_preset(self, temp_config_dir):
        """Test saving project config when no current preset."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.save_project_config()
        assert "No current preset to save" in str(exc_info.value)

    def test_save_project_config_nonexistent_preset(self, temp_config_dir):
        """Test saving project config with nonexistent preset."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.save_project_config(preset_name="nonexistent")
        assert "does not exist" in str(exc_info.value)

    def test_load_project_config_no_file(self, temp_config_dir):
        """Test loading project config when no file exists."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.load_project_config()
        assert "No project configuration found" in str(exc_info.value)

    def test_load_project_config_nonexistent_preset(self, temp_config_dir):
        """Test loading project config with nonexistent preset reference."""
        # Mock project config that references non-existent preset
        mock_project_config = ProjectConfig(preset="nonexistent", overrides={})
        with patch.object(self.preset_manager.config_manager, 'get_project_config', return_value=mock_project_config):
            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.load_project_config()
            assert "not found" in str(exc_info.value)

    def test_load_project_config_invalid_overrides(self, temp_config_dir):
        """Test loading project config with invalid overrides."""
        self.preset_manager.add_preset("test", "key", "url")
        mock_project_config = ProjectConfig(preset="test", overrides={"INVALID": "value"})

        with patch.object(self.preset_manager.config_manager, 'get_project_config', return_value=mock_project_config):
            with patch.object(self.preset_manager.env_manager, 'validate_env_variables') as mock_validate:
                mock_validate.side_effect = ValueError("Invalid overrides")

                with pytest.raises(ValueError) as exc_info:
                    self.preset_manager.load_project_config()
                assert "Invalid project config overrides" in str(exc_info.value)

    def test_load_project_config_without_apply_to_env(self, temp_config_dir):
        """Test loading project config without applying to environment."""
        self.preset_manager.add_preset("test", "key", "url")
        mock_project_config = ProjectConfig(preset="test", overrides={"API_MODEL": "custom"})

        with patch.object(self.preset_manager.config_manager, 'get_project_config', return_value=mock_project_config):
            preset, applied_vars, cleared_vars = self.preset_manager.load_project_config(apply_to_env=False)

            assert preset.variables["API_MODEL"] == "custom"
            assert applied_vars == {}
            assert cleared_vars == []

    def test_get_status_with_project_config(self, temp_config_dir):
        """Test getting status with project config."""
        self.preset_manager.add_preset("test", "key", "url")
        self.preset_manager.use_preset("test")

        mock_project_config = ProjectConfig(preset="test", overrides={})
        with patch.object(self.preset_manager.config_manager, 'get_project_config', return_value=mock_project_config):
            status = self.preset_manager.get_status()

        assert status["current_preset"] == "test"
        assert status["project_config"] is not None
        assert status["current_preset_details"]["name"] == "test"

    def test_get_status_without_current_preset(self, temp_config_dir):
        """Test getting status without current preset."""
        status = self.preset_manager.get_status()

        assert status["current_preset"] is None
        assert "current_preset_details" not in status
        assert status["total_presets"] == 0

    def test_export_preset_nonexistent(self, temp_config_dir):
        """Test exporting nonexistent preset."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.export_preset("nonexistent")
        assert "not found" in str(exc_info.value)

    def test_export_preset_with_secrets(self, temp_config_dir):
        """Test exporting preset with secrets redacted."""
        self.preset_manager.add_preset_flexible("test", {
            "API_KEY": "secret-key",
            "API_TOKEN": "secret-token",
            "SECRET_VALUE": "secret",
            "NORMAL_VALUE": "normal"
        })

        export_data = self.preset_manager.export_preset("test", redact_secrets=True)

        assert export_data["variables"]["API_KEY"] == "***REDACTED***"
        assert export_data["variables"]["API_TOKEN"] == "***REDACTED***"
        assert export_data["variables"]["SECRET_VALUE"] == "***REDACTED***"
        assert export_data["variables"]["NORMAL_VALUE"] == "normal"

    def test_export_preset_without_redaction(self, temp_config_dir):
        """Test exporting preset without redacting secrets."""
        self.preset_manager.add_preset_flexible("test", {
            "API_KEY": "secret-key",
            "NORMAL_VALUE": "normal"
        })

        export_data = self.preset_manager.export_preset("test", redact_secrets=False)

        assert export_data["variables"]["API_KEY"] == "secret-key"
        assert export_data["variables"]["NORMAL_VALUE"] == "normal"

    def test_export_all_presets_empty(self, temp_config_dir):
        """Test exporting all presets when none exist."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.export_all_presets()
        assert "No presets found to export" in str(exc_info.value)

    def test_export_all_presets_to_file(self, temp_config_dir):
        """Test exporting all presets to file."""
        self.preset_manager.add_preset("test1", "key1", "url1")
        self.preset_manager.add_preset("test2", "key2", "url2")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            output_file = Path(f.name)

        try:
            export_data = self.preset_manager.export_all_presets(output_file=output_file)

            assert output_file.exists()
            with open(output_file, 'r') as f:
                file_data = json.load(f)

            assert file_data["version"] == "1.0.0"
            assert len(file_data["presets"]) == 2
            assert file_data == export_data
        finally:
            output_file.unlink()

    def test_export_preset_to_file(self, temp_config_dir):
        """Test exporting single preset to file."""
        self.preset_manager.add_preset("test", "key", "url")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            output_file = Path(f.name)

        try:
            self.preset_manager.export_preset_to_file("test", output_file)

            assert output_file.exists()
            with open(output_file, 'r') as f:
                file_data = json.load(f)

            assert file_data["version"] == "1.0.0"
            assert file_data["preset"]["name"] == "test"
        finally:
            output_file.unlink()

    def test_import_preset_invalid_data(self, temp_config_dir):
        """Test importing preset with invalid data."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.import_preset({"invalid": "data"})
        assert "Invalid preset data" in str(exc_info.value)

    def test_import_preset_already_exists(self, temp_config_dir):
        """Test importing preset that already exists."""
        self.preset_manager.add_preset("existing", "key", "url")

        preset_data = {
            "name": "existing",
            "variables": {"API_KEY": "new-key", "API_BASE_URL": "new-url"},
            "description": "",
            "tags": [],
            "created_at": "2023-01-01T00:00:00"
        }

        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.import_preset(preset_data, allow_overwrite=False)
        assert "already exists" in str(exc_info.value)

    def test_import_preset_with_redacted_values(self, temp_config_dir):
        """Test importing preset with redacted values."""
        preset_data = {
            "name": "test",
            "variables": {"API_KEY": "***REDACTED***"},
            "description": "",
            "tags": [],
            "created_at": "2023-01-01T00:00:00"
        }

        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.import_preset(preset_data)
        assert "redacted value" in str(exc_info.value)

    def test_import_preset_invalid_variables(self, temp_config_dir):
        """Test importing preset with invalid variables."""
        preset_data = {
            "name": "test",
            "variables": {"INVALID": "value"},
            "description": "",
            "tags": [],
            "created_at": "2023-01-01T00:00:00"
        }

        with patch.object(self.preset_manager.env_manager, 'validate_env_variables') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid variables")

            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.import_preset(preset_data)
            assert "Invalid preset variables" in str(exc_info.value)

    def test_import_from_file_not_found(self, temp_config_dir):
        """Test importing from nonexistent file."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.import_from_file(Path("/nonexistent/file.json"))
        assert "not found" in str(exc_info.value)

    def test_import_from_file_invalid_json(self, temp_config_dir):
        """Test importing from file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json content")
            temp_file = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.import_from_file(temp_file)
            assert "Invalid JSON format" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_import_from_file_single_preset(self, temp_config_dir):
        """Test importing single preset from file."""
        preset_data = {
            "version": "1.0.0",
            "preset": {
                "name": "imported",
                "variables": {"API_KEY": "key", "API_BASE_URL": "url"},
                "description": "Imported preset",
                "tags": [],
                "created_at": "2023-01-01T00:00:00"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(preset_data, f)
            temp_file = Path(f.name)

        try:
            imported_presets = self.preset_manager.import_from_file(temp_file)

            assert len(imported_presets) == 1
            assert imported_presets[0].name == "imported"
        finally:
            temp_file.unlink()

    def test_import_from_file_multiple_presets(self, temp_config_dir):
        """Test importing multiple presets from file."""
        preset_data = {
            "version": "1.0.0",
            "presets": [
                {
                    "name": "preset1",
                    "variables": {"API_KEY": "key1", "API_BASE_URL": "url1"},
                    "description": "",
                    "tags": [],
                    "created_at": "2023-01-01T00:00:00"
                },
                {
                    "name": "preset2",
                    "variables": {"API_KEY": "key2", "API_BASE_URL": "url2"},
                    "description": "",
                    "tags": [],
                    "created_at": "2023-01-01T00:00:00"
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(preset_data, f)
            temp_file = Path(f.name)

        try:
            imported_presets = self.preset_manager.import_from_file(temp_file)

            assert len(imported_presets) == 2
            assert imported_presets[0].name == "preset1"
            assert imported_presets[1].name == "preset2"
        finally:
            temp_file.unlink()

    def test_import_from_file_invalid_format(self, temp_config_dir):
        """Test importing from file with invalid format."""
        invalid_data = {"invalid": "format"}

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(invalid_data, f)
            temp_file = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.import_from_file(temp_file)
            assert "Invalid import file format" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_update_preset_nonexistent(self, temp_config_dir):
        """Test updating nonexistent preset."""
        with pytest.raises(ValueError) as exc_info:
            self.preset_manager.update_preset("nonexistent", api_key="new-key")
        assert "not found" in str(exc_info.value)

    def test_update_preset_api_fields(self, temp_config_dir):
        """Test updating preset with API fields."""
        self.preset_manager.add_preset("test", "old-key", "old-url")

        updated_preset = self.preset_manager.update_preset(
            "test",
            api_key="new-key",
            base_url="new-url",
            model="new-model",
            description="Updated description",
            tags=["updated", "tags"]
        )

        assert updated_preset.variables["API_KEY"] == "new-key"
        assert updated_preset.variables["API_BASE_URL"] == "new-url"
        assert updated_preset.variables["API_MODEL"] == "new-model"
        assert updated_preset.description == "Updated description"
        assert updated_preset.tags == ["updated", "tags"]

    def test_update_preset_invalid_variables(self, temp_config_dir):
        """Test updating preset with invalid variables."""
        self.preset_manager.add_preset("test", "key", "url")

        with patch.object(self.preset_manager.env_manager, 'validate_env_variables') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid configuration")

            with pytest.raises(ValueError) as exc_info:
                self.preset_manager.update_preset("test", api_key="invalid")
            assert "Invalid configuration" in str(exc_info.value)

    def test_update_preset_current_preset(self, temp_config_dir):
        """Test updating the current preset."""
        self.preset_manager.add_preset("current", "old-key", "old-url")
        self.preset_manager.use_preset("current")

        updated_preset = self.preset_manager.update_preset("current", api_key="new-key")

        # Check that current config is also updated
        current = self.preset_manager.get_current_preset()
        assert current.variables["API_KEY"] == "new-key"