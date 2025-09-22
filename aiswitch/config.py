from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class PresetConfig(BaseModel):
    name: str
    description: str = ""
    variables: Dict[str, str]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = Field(default_factory=list)


class GlobalConfig(BaseModel):
    version: str = "1.0.0"
    current_preset: Optional[str] = None
    default_variables: List[str] = Field(default_factory=lambda: ["API_KEY", "API_BASE_URL", "API_MODEL"])


class ProjectConfig(BaseModel):
    preset: str
    overrides: Dict[str, str] = Field(default_factory=dict)


class ConfigManager:
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.presets_dir = self.config_dir / "presets"
        self.global_config_path = self.config_dir / "config.yaml"
        self.current_config_path = self.config_dir / "current.yaml"
        self.project_config_name = ".aiswitch.yaml"
        self.ensure_config_dir()

    def _get_config_dir(self) -> Path:
        import platform
        if platform.system() == "Windows":
            return Path.home() / "AppData" / "Roaming" / "aiswitch"
        else:
            return Path.home() / ".config" / "aiswitch"

    def ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        if not self.global_config_path.exists():
            self.save_global_config(GlobalConfig())

    def get_global_config(self) -> GlobalConfig:
        try:
            if self.global_config_path.exists():
                with open(self.global_config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return GlobalConfig(**data) if data else GlobalConfig()
        except Exception:
            pass
        return GlobalConfig()

    def save_global_config(self, config: GlobalConfig):
        with open(self.global_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False)

    def get_preset(self, name: str) -> Optional[PresetConfig]:
        preset_path = self.presets_dir / f"{name}.yaml"
        if not preset_path.exists():
            return None

        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return PresetConfig(**data)
        except Exception:
            return None

    def save_preset(self, preset: PresetConfig):
        preset_path = self.presets_dir / f"{preset.name}.yaml"

        preset_path.parent.mkdir(parents=True, exist_ok=True)

        with open(preset_path, 'w', encoding='utf-8') as f:
            yaml.dump(preset.model_dump(), f, default_flow_style=False)

        preset_path.chmod(0o600)

    def delete_preset(self, name: str) -> bool:
        preset_path = self.presets_dir / f"{name}.yaml"
        if preset_path.exists():
            preset_path.unlink()
            return True
        return False

    def list_presets(self) -> List[str]:
        if not self.presets_dir.exists():
            return []

        presets = []
        for preset_file in self.presets_dir.glob("*.yaml"):
            presets.append(preset_file.stem)
        return sorted(presets)

    def get_current_config(self) -> Optional[PresetConfig]:
        if self.current_config_path.exists():
            try:
                with open(self.current_config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return PresetConfig(**data) if data else None
            except Exception:
                pass
        return None

    def save_current_config(self, preset: PresetConfig):
        with open(self.current_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(preset.model_dump(), f, default_flow_style=False)
        self.current_config_path.chmod(0o600)

    def clear_current_config(self):
        if self.current_config_path.exists():
            self.current_config_path.unlink()

    def get_project_config(self, project_dir: Optional[Path] = None) -> Optional[ProjectConfig]:
        if project_dir is None:
            project_dir = Path.cwd()

        project_config_path = project_dir / self.project_config_name
        if not project_config_path.exists():
            return None

        try:
            with open(project_config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return ProjectConfig(**data) if data else None
        except Exception:
            return None

    def save_project_config(self, config: ProjectConfig, project_dir: Optional[Path] = None):
        if project_dir is None:
            project_dir = Path.cwd()

        project_config_path = project_dir / self.project_config_name
        with open(project_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False)

    def preset_exists(self, name: str) -> bool:
        return (self.presets_dir / f"{name}.yaml").exists()

    def get_similar_preset_names(self, name: str) -> List[str]:
        all_presets = self.list_presets()
        similar = []

        name_lower = name.lower()
        for preset in all_presets:
            preset_lower = preset.lower()
            if (name_lower in preset_lower or
                preset_lower in name_lower or
                abs(len(name_lower) - len(preset_lower)) <= 2):
                similar.append(preset)

        return similar[:3]