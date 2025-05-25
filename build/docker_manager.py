"""
Docker build and push management module
"""
import subprocess
import sys
import os
import logging
from typing import Any


class DockerManager:
    """Manages Docker image building and pushing to Google Artifact Registry"""
    
    def __init__(self, logger: logging.Logger, gcloud_path: str | None):
        self.logger = logger
        self.gcloud_path = gcloud_path
    
    def run_command(self, command: list[str], check: bool = True) -> Any:
        """Run a shell command"""
        try:
            self.logger.debug(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=check,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error: {e}")
            if check:
                sys.exit(1)
            raise
    
    def configure_docker_for_gar(self, gar_location: str):
        """Configure Docker for Google Artifact Registry"""
        if not self.gcloud_path:
            self.logger.error("gcloud CLI not found. Cannot configure Docker for Google Artifact Registry.")
            sys.exit(1)
        
        try:
            self.run_command([self.gcloud_path, "auth", "configure-docker", f"{gar_location}-docker.pkg.dev"])
            self.logger.info("Docker configured for Google Artifact Registry.")
        except subprocess.CalledProcessError:
            self.logger.error("Failed to configure Docker for Google Artifact Registry")
            sys.exit(1)
    
    def build_image(self, image_tag: str):
        """Build Docker image"""
        self.logger.info("Building Docker image...")
        try:
            self.run_command(["docker", "build", "-t", image_tag, "."])
            self.logger.info(f"Docker image built successfully: {image_tag}")
        except subprocess.CalledProcessError:
            self.logger.error("Docker image build failed")
            sys.exit(1)
    
    def push_image(self, image_tag: str):
        """Push Docker image to registry"""
        self.logger.info("Pushing Docker image to Google Artifact Registry...")
        try:
            self.run_command(["docker", "push", image_tag])
            self.logger.info(f"Docker image pushed successfully: {image_tag}")
        except subprocess.CalledProcessError:
            self.logger.error("Docker image push failed")
            sys.exit(1)
    
    def build_and_push_image(self):
        """Build and push Docker image to Google Artifact Registry"""
        # Configure Docker for GAR
        gar_location = os.environ["GAR_LOCATION"]
        self.configure_docker_for_gar(gar_location)
        
        # Build image
        image_tag = f"{gar_location}-docker.pkg.dev/{os.environ['GCP_PROJECT_ID']}/{os.environ['GAR_REPOSITORY']}/{os.environ['IMAGE_NAME']}:{os.environ['IMAGE_TAG']}"
        
        self.build_image(image_tag)
        self.push_image(image_tag)
        
        self.logger.info("Docker image build and push completed successfully.")
