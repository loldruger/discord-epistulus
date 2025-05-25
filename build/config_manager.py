"""
Configuration management module for build system
"""
import json
import os
import sys
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_file = project_root / "build_config.json"
        self.config = self.load_config()
    
    def load_config(self) -> dict[str, Any]:
        """Load configuration from config.json"""
        # Create default config if it doesn't exist
        if not self.config_file.exists():
            default_config = {
                "gcp": {
                    "project_id": "",
                    "region": "asia-northeast3",
                    "artifact_registry": {
                        "location": "asia-northeast3",
                        "repository": "discord-epistulus-repo"
                    }
                },
                "docker": {
                    "image_name": "discord-epistulus",
                    "image_tag": "latest"
                }
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default config file: {self.config_file}")
            print("Please update the configuration file with your project details")
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading config file: {e}")
            sys.exit(1)
    
    def validate_config(self):
        """Validate that required configuration values are set"""
        required_env_vars = {
            "GAR_LOCATION": self.config["gcp"]["artifact_registry"]["location"],
            "GCP_PROJECT_ID": self.config["gcp"]["project_id"],
            "GAR_REPOSITORY": self.config["gcp"]["artifact_registry"]["repository"],
            "IMAGE_NAME": self.config["docker"]["image_name"],
            "IMAGE_TAG": self.config["docker"]["image_tag"]
        }
        
        # Check environment variables first, then fall back to config
        missing_vars: list[str] = []
        for var_name, config_value in required_env_vars.items():
            if var_name not in os.environ:
                if not config_value:
                    missing_vars.append(var_name)
                else:
                    os.environ[var_name] = config_value
                    
        if missing_vars:
            print(f"Missing required configuration: {', '.join(missing_vars)}")
            print("Please set these in environment variables or update build_config.json")
            sys.exit(1)
    
    def get_config(self) -> dict[str, Any]:
        """Get the loaded configuration"""
        return self.config
