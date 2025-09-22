import os
import subprocess
import platform
from typing import Dict, List, Optional
from pathlib import Path

from .config import PresetConfig


class EnvManager:
    def __init__(self):
        self.default_variables = ["API_KEY", "API_BASE_URL", "API_MODEL"]
        self.system = platform.system()

    def apply_preset(self, preset: PresetConfig) -> Dict[str, str]:
        applied_vars = {}
        for key, value in preset.variables.items():
            os.environ[key] = value
            applied_vars[key] = value
        return applied_vars

    def clear_variables(self, variables: Optional[List[str]] = None) -> List[str]:
        if variables is None:
            variables = self.default_variables

        cleared_vars = []
        for var in variables:
            if var in os.environ:
                del os.environ[var]
                cleared_vars.append(var)
        return cleared_vars

    def get_current_env(self, variables: Optional[List[str]] = None) -> Dict[str, str]:
        if variables is None:
            variables = self.default_variables

        return {var: os.environ.get(var, "") for var in variables}

    def has_env_variables(self, variables: Optional[List[str]] = None) -> bool:
        if variables is None:
            variables = self.default_variables

        return any(var in os.environ and os.environ[var] for var in variables)

    def validate_env_variables(self, variables: Dict[str, str]) -> Dict[str, str]:
        validated = {}
        errors = {}

        for key, value in variables.items():
            if not value.strip():
                errors[key] = "Value cannot be empty"
                continue

            if key == "API_BASE_URL":
                if not value.startswith(("http://", "https://")):
                    errors[key] = "URL must start with http:// or https://"
                    continue
                if value.endswith("/"):
                    value = value.rstrip("/")

            validated[key] = value

        if errors:
            raise ValueError(f"Validation errors: {errors}")

        return validated

    def export_to_shell(self, variables: Dict[str, str], shell_file: Optional[Path] = None) -> bool:
        if self.system == "Windows":
            return self._export_to_windows_env(variables)
        else:
            return self._export_to_unix_shell(variables, shell_file)

    def _export_to_unix_shell(self, variables: Dict[str, str], shell_file: Optional[Path] = None) -> bool:
        if shell_file is None:
            shell_file = self._detect_shell_config()

        if not shell_file or not shell_file.exists():
            return False

        try:
            export_lines = []
            for key, value in variables.items():
                export_lines.append(f'export {key}="{value}"')

            with open(shell_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(['', '# AISwitch environment variables'] + export_lines + ['']))

            return True
        except Exception:
            return False

    def _export_to_windows_env(self, variables: Dict[str, str]) -> bool:
        try:
            for key, value in variables.items():
                subprocess.run([
                    'setx', key, value
                ], check=True, capture_output=True, text=True)
            return True
        except Exception:
            return False

    def _detect_shell_config(self) -> Optional[Path]:
        home = Path.home()
        shell_configs = [
            home / ".bashrc",
            home / ".zshrc",
            home / ".profile",
            home / ".bash_profile"
        ]

        shell = os.environ.get('SHELL', '')
        if 'zsh' in shell:
            shell_configs.insert(0, home / ".zshrc")
        elif 'bash' in shell:
            shell_configs.insert(0, home / ".bashrc")

        for config in shell_configs:
            if config.exists():
                return config

        return shell_configs[0]

    def get_env_info(self) -> Dict[str, str]:
        info = {
            "system": self.system,
            "shell": os.environ.get('SHELL', 'unknown'),
            "config_detected": str(self._detect_shell_config()) if self.system != "Windows" else "Windows Registry"
        }

        current_env = self.get_current_env()
        for var, value in current_env.items():
            if value:
                info[f"current_{var}"] = "***" if "KEY" in var else value

        return info