from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .config import ConfigManager, PresetConfig, ProjectConfig, GlobalConfig
from .env import EnvManager


class PresetManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.env_manager = EnvManager()

    def add_preset_flexible(self, name: str, variables: Dict[str, str],
                           description: str = "", tags: Optional[List[str]] = None) -> PresetConfig:
        """添加新的预设配置，支持任意环境变量"""
        if self.config_manager.preset_exists(name):
            raise ValueError(f"Preset '{name}' already exists")

        if not variables:
            raise ValueError("At least one environment variable must be provided")

        try:
            validated_vars = self.env_manager.validate_env_variables(variables)
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {e}")

        preset = PresetConfig(
            name=name,
            description=description,
            variables=validated_vars,
            tags=tags or []
        )

        self.config_manager.save_preset(preset)
        return preset

    def add_preset(self, name: str, api_key: str, base_url: str,
                   model: Optional[str] = None, description: str = "",
                   tags: Optional[List[str]] = None) -> PresetConfig:
        if self.config_manager.preset_exists(name):
            raise ValueError(f"Preset '{name}' already exists")

        variables = {
            "API_KEY": api_key,
            "API_BASE_URL": base_url
        }

        if model:
            variables["API_MODEL"] = model

        try:
            validated_vars = self.env_manager.validate_env_variables(variables)
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {e}")

        preset = PresetConfig(
            name=name,
            description=description,
            variables=validated_vars,
            tags=tags or []
        )

        self.config_manager.save_preset(preset)
        return preset

    def remove_preset(self, name: str) -> bool:
        if not self.config_manager.preset_exists(name):
            return False

        global_config = self.config_manager.get_global_config()
        if global_config.current_preset == name:
            global_config.current_preset = None
            self.config_manager.save_global_config(global_config)
            self.config_manager.clear_current_config()

        return self.config_manager.delete_preset(name)

    def use_preset(self, name: str, apply_to_env: bool = True) -> Tuple[PresetConfig, Dict[str, str]]:
        preset = self.config_manager.get_preset(name)
        if not preset:
            similar = self.config_manager.get_similar_preset_names(name)
            if similar:
                raise ValueError(f"Preset '{name}' not found. Did you mean: {', '.join(similar)}?")
            else:
                raise ValueError(f"Preset '{name}' not found. Use 'aiswitch list' to see available presets.")

        applied_vars = {}
        if apply_to_env:
            applied_vars = self.env_manager.apply_preset(preset)

        self.config_manager.save_current_config(preset)

        global_config = self.config_manager.get_global_config()
        global_config.current_preset = name
        self.config_manager.save_global_config(global_config)

        return preset, applied_vars

    def list_presets(self) -> List[Tuple[str, PresetConfig]]:
        preset_names = self.config_manager.list_presets()
        presets = []

        for name in preset_names:
            preset = self.config_manager.get_preset(name)
            if preset:
                presets.append((name, preset))

        return presets

    def get_current_preset(self) -> Optional[PresetConfig]:
        return self.config_manager.get_current_config()

    def clear_current(self) -> List[str]:
        current = self.get_current_preset()
        if current:
            cleared_vars = self.env_manager.clear_variables(list(current.variables.keys()))
        else:
            cleared_vars = self.env_manager.clear_variables()

        self.config_manager.clear_current_config()

        global_config = self.config_manager.get_global_config()
        global_config.current_preset = None
        self.config_manager.save_global_config(global_config)

        return cleared_vars

    def save_project_config(self, preset_name: Optional[str] = None,
                           overrides: Optional[Dict[str, str]] = None,
                           project_dir: Optional[Path] = None) -> ProjectConfig:
        if preset_name is None:
            current = self.get_current_preset()
            if not current:
                raise ValueError("No current preset to save. Use 'aiswitch use <preset>' first.")
            preset_name = current.name

        if not self.config_manager.preset_exists(preset_name):
            raise ValueError(f"Preset '{preset_name}' does not exist")

        project_config = ProjectConfig(
            preset=preset_name,
            overrides=overrides or {}
        )

        self.config_manager.save_project_config(project_config, project_dir)
        return project_config

    def load_project_config(self, project_dir: Optional[Path] = None,
                           apply_to_env: bool = True) -> Tuple[PresetConfig, Dict[str, str]]:
        project_config = self.config_manager.get_project_config(project_dir)
        if not project_config:
            raise ValueError("No project configuration found (.aiswitch.yaml)")

        preset = self.config_manager.get_preset(project_config.preset)
        if not preset:
            raise ValueError(f"Preset '{project_config.preset}' referenced in project config not found")

        merged_variables = preset.variables.copy()
        merged_variables.update(project_config.overrides)

        if project_config.overrides:
            try:
                validated_overrides = self.env_manager.validate_env_variables(project_config.overrides)
                merged_variables.update(validated_overrides)
            except ValueError as e:
                raise ValueError(f"Invalid project config overrides: {e}")

        merged_preset = PresetConfig(
            name=preset.name,
            description=preset.description,
            variables=merged_variables,
            created_at=preset.created_at,
            tags=preset.tags
        )

        applied_vars = {}
        if apply_to_env:
            applied_vars = self.env_manager.apply_preset(merged_preset)

        self.config_manager.save_current_config(merged_preset)

        global_config = self.config_manager.get_global_config()
        global_config.current_preset = project_config.preset
        self.config_manager.save_global_config(global_config)

        return merged_preset, applied_vars

    def get_status(self) -> Dict[str, any]:
        current_preset = self.get_current_preset()
        env_info = self.env_manager.get_env_info()

        project_config = self.config_manager.get_project_config()

        status = {
            "current_preset": current_preset.name if current_preset else None,
            "environment_variables": env_info,
            "config_directory": str(self.config_manager.config_dir),
            "project_config": project_config.model_dump() if project_config else None,
            "total_presets": len(self.config_manager.list_presets())
        }

        if current_preset:
            status["current_preset_details"] = {
                "name": current_preset.name,
                "description": current_preset.description,
                "created_at": current_preset.created_at,
                "tags": current_preset.tags,
                "variables_count": len(current_preset.variables)
            }

        return status

    def export_preset(self, name: str) -> Dict:
        preset = self.config_manager.get_preset(name)
        if not preset:
            raise ValueError(f"Preset '{name}' not found")

        export_data = preset.model_dump()

        for key in export_data["variables"]:
            if "KEY" in key.upper():
                export_data["variables"][key] = "***REDACTED***"

        return export_data

    def import_preset(self, preset_data: Dict, allow_overwrite: bool = False) -> PresetConfig:
        try:
            preset = PresetConfig(**preset_data)
        except Exception as e:
            raise ValueError(f"Invalid preset data: {e}")

        if self.config_manager.preset_exists(preset.name) and not allow_overwrite:
            raise ValueError(f"Preset '{preset.name}' already exists. Use --force to overwrite.")

        try:
            validated_vars = self.env_manager.validate_env_variables(preset.variables)
            preset.variables = validated_vars
        except ValueError as e:
            raise ValueError(f"Invalid preset variables: {e}")

        self.config_manager.save_preset(preset)
        return preset

    def update_preset(self, name: str, **kwargs) -> PresetConfig:
        preset = self.config_manager.get_preset(name)
        if not preset:
            raise ValueError(f"Preset '{name}' not found")

        update_data = preset.model_dump()

        for key, value in kwargs.items():
            if key in ["api_key", "base_url", "model"]:
                var_name = {
                    "api_key": "API_KEY",
                    "base_url": "API_BASE_URL",
                    "model": "API_MODEL"
                }[key]
                update_data["variables"][var_name] = value
            elif key in ["description", "tags"]:
                update_data[key] = value

        try:
            validated_vars = self.env_manager.validate_env_variables(update_data["variables"])
            update_data["variables"] = validated_vars
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {e}")

        updated_preset = PresetConfig(**update_data)
        self.config_manager.save_preset(updated_preset)

        current = self.get_current_preset()
        if current and current.name == name:
            self.config_manager.save_current_config(updated_preset)

        return updated_preset