#!/usr/bin/env python3
"""
Google Cloud development environment setup script
"""

import logging
import sys
from pathlib import Path

from build.config_manager import ConfigManager
from build.prerequisite_checker import PrerequisiteChecker
from build.gcloud_manager import GCloudManager
from build.docker_manager import DockerManager

class BuildManager:
    """Main orchestrator for the build process"""
    
    def __init__(self):
        self.setup_logging()
        self.project_root = Path(__file__).parent
        
        # Initialize modular components
        self.config_manager = ConfigManager(self.project_root)
        self.prerequisite_checker = PrerequisiteChecker(self.logger)
        self.gcloud_manager = GCloudManager(self.logger, self.config_manager.get_config())
        self.docker_manager = None  # Will be initialized after gcloud setup
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    def run(self):
        """Main execution flow"""
        try:
            # Check prerequisites
            self.prerequisite_checker.check_all(self.config_manager.get_config())
            
            # Setup gcloud
            self.gcloud_manager.setup_gcloud()
            self.gcloud_manager.authenticate_gcloud()
            
            # Initialize Docker manager with gcloud path
            self.docker_manager = DockerManager(
                self.logger, 
                self.gcloud_manager.get_gcloud_path()
            )
            
            # Validate configuration and build/push image
            self.config_manager.validate_config()
            self.docker_manager.build_and_push_image()
            
            self.logger.info("Build process completed successfully!")
            
        except KeyboardInterrupt:
            self.logger.info("Build process interrupted by user.")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            sys.exit(1)


def main():
    """Main entry point"""
    manager = BuildManager()
    manager.run()


if __name__ == "__main__":
    main()
