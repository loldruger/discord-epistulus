"""
Configuration management module for deployment system
"""
import json
import os
import sys
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages configuration loading, validation, and environment setup"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_file = project_root / "build_config.json"
        self.config = self.load_config()
    
    def load_config(self) -> dict[str, Any]:
        """Load configuration from build_config.json"""
        # Create default config if it doesn't exist
        if not self.config_file.exists():
            default_config = self._get_default_config()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"✅ 기본 설정 파일 생성: {self.config_file}")
            print("📝 프로젝트 세부사항으로 설정 파일을 업데이트해주세요")
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"❌ 설정 파일 로드 오류: {e}")
            sys.exit(1)
    
    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration values"""
        return {
            "gcp": {
                "project_id": "",
                "region": "asia-northeast3",
                "artifact_registry": {
                    "location": "asia-northeast3",
                    "repository": "discord-epistulus-repo"
                },
                "cloud_run": {
                    "service_name": "discord-epistulus",
                    "memory": "512Mi",
                    "cpu": "1",
                    "min_instances": 0,
                    "max_instances": 10
                }
            },
            "docker": {
                "image_name": "discord-epistulus",
                "image_tag": "latest"
            },
            "github": {
                "repository": "",
                "secrets": {
                    "GCP_PROJECT_ID": True,
                    "GAR_LOCATION": True,
                    "GAR_REPOSITORY": True,
                    "IMAGE_NAME": True,
                    "IMAGE_TAG": True
                }
            },
            "scripts": {
                "gcloud_installation": "build/gcloud_installation.py",
                "gcloud_reinit": "build/gcloud_reinit.py"
            }
        }
    
    def validate_config(self) -> bool:
        """Validate that required configuration values are set"""
        required_configs = {
            "gcp.project_id": self.config.get("gcp", {}).get("project_id"),
            "gcp.region": self.config.get("gcp", {}).get("region"),
            "docker.image_name": self.config.get("docker", {}).get("image_name")
        }
        
        missing_configs = [key for key, value in required_configs.items() if not value]
        
        if missing_configs:
            print(f"❌ 필수 설정값 누락: {', '.join(missing_configs)}")
            print(f"📝 {self.config_file}을 업데이트해주세요")
            return False
            
        return True
    
    def setup_environment_variables(self) -> None:
        """Setup environment variables from configuration"""
        env_mappings = {
            "GAR_LOCATION": self.config["gcp"]["artifact_registry"]["location"],
            "GCP_PROJECT_ID": self.config["gcp"]["project_id"],
            "GAR_REPOSITORY": self.config["gcp"]["artifact_registry"]["repository"],
            "IMAGE_NAME": self.config["docker"]["image_name"],
            "IMAGE_TAG": self.config["docker"]["image_tag"],
            "GCP_REGION": self.config["gcp"]["region"]
        }
        
        set_vars: list[str] = []
        for var_name, config_value in env_mappings.items():
            if var_name not in os.environ and config_value:
                os.environ[var_name] = str(config_value)
                set_vars.append(var_name)
        
        if set_vars:
            print(f"🔧 환경 변수 설정: {', '.join(set_vars)}")
    
    def get_config(self) -> dict[str, Any]:
        """Get the loaded configuration"""
        return self.config
    
    def get_gcp_config(self) -> dict[str, Any]:
        """Get GCP-specific configuration"""
        return self.config.get("gcp", {})
    
    def get_docker_config(self) -> dict[str, Any]:
        """Get Docker-specific configuration"""
        return self.config.get("docker", {})
    
    def get_github_config(self) -> dict[str, Any]:
        """Get GitHub-specific configuration"""
        return self.config.get("github", {})
    
    def update_config(self, section: str, key: str, value: Any) -> None:
        """Update a specific configuration value"""
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = value
        
        # Save to file
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        print(f"📝 설정 업데이트: {section}.{key} = {value}")
