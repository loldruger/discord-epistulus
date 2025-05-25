"""
Prerequisites checking module for build system
"""
import subprocess
import sys
import shutil
import logging
from typing import Any


class PrerequisiteChecker:
    """Checks system prerequisites for the build process"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        return shutil.which(command) is not None
    
    def run_command(self, command: list[str], capture_output: bool = False) -> Any:
        """Run a shell command for checking purposes"""
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=capture_output,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            raise e
    
    def check_python_version(self):
        """Check Python version requirements"""
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            self.logger.error(f"Python 3.8+ is required. Current version: {python_version.major}.{python_version.minor}")
            sys.exit(1)
        self.logger.info(f"Python version check: OK ({python_version.major}.{python_version.minor}.{python_version.micro})")
    
    def check_docker(self):
        """Check Docker CLI and daemon"""
        # Check Docker CLI
        if not self.check_command_exists("docker"):
            self.logger.error("Docker is not installed. Please install Docker. (https://docs.docker.com/engine/install/)")
            sys.exit(1)
        self.logger.info("Docker CLI check: OK.")
        
        # Check Docker daemon
        try:
            self.run_command(["docker", "info"], capture_output=True)
            self.logger.info("Docker daemon status check: OK.")
        except subprocess.CalledProcessError:
            self.logger.error("Docker daemon is not running. Please start Docker daemon.")
            sys.exit(1)
    
    def check_optional_scripts(self, config: dict[str, Any]):
        """Check if optional fallback scripts exist"""
        if "scripts" in config:
            from pathlib import Path
            
            gcloud_installation_script = Path(config["scripts"].get("gcloud_installation", ""))
            if gcloud_installation_script and gcloud_installation_script.exists():
                self.logger.info(f"Found fallback gcloud installation script: {gcloud_installation_script}")
                
            gcloud_reinit_script = Path(config["scripts"].get("gcloud_reinit", ""))
            if gcloud_reinit_script and gcloud_reinit_script.exists():
                self.logger.info(f"Found fallback gcloud reinit script: {gcloud_reinit_script}")
    
    def check_all(self, config: dict[str, Any] | None = None):
        """Run all prerequisite checks"""
        self.logger.info("Checking prerequisites...")
        
        self.check_python_version()
        self.check_docker()
        
        if config:
            self.check_optional_scripts(config)
            
        self.logger.info("All prerequisite checks passed.")
