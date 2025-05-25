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
    
    def run_command(self, command: list[str], check: bool = True, capture_output: bool = False) -> Any:
        """Run a shell command"""
        try:
            self.logger.debug(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=check,
                text=True,
                capture_output=capture_output
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
            self.run_command([str(self.gcloud_path), "auth", "configure-docker", f"{gar_location}-docker.pkg.dev"])
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
    
    def create_artifact_registry_repository(self, project_id: str, location: str, repo_name: str):
        """Create Google Artifact Registry repository if it doesn't exist"""
        if not self.gcloud_path:
            self.logger.error("gcloud CLI not found. Cannot create Artifact Registry repository.")
            sys.exit(1)
        
        # Check if repository already exists
        try:
            result = self.run_command([
                str(self.gcloud_path), "artifacts", "repositories", "describe", repo_name,
                "--location", location,
                "--project", project_id
            ], check=False, capture_output=True)
            
            if result.returncode == 0:
                self.logger.info(f"Artifact Registry repository '{repo_name}' already exists.")
                return
        except subprocess.CalledProcessError:
            pass  # Repository doesn't exist, create it
        
        # Create repository
        self.logger.info(f"Creating Artifact Registry repository: {repo_name}")
        try:
            self.run_command([
                str(self.gcloud_path), "artifacts", "repositories", "create", repo_name,
                "--repository-format=docker",
                "--location", location,
                "--project", project_id,
                "--description", "Repository for Discord bot container images"
            ])
            self.logger.info(f"Artifact Registry repository '{repo_name}' created successfully.")
        except subprocess.CalledProcessError:
            self.logger.error(f"Failed to create Artifact Registry repository: {repo_name}")
            sys.exit(1)

    def build_and_push_image(self) -> str:
        """Build and push Docker image to Google Artifact Registry"""
        # Get environment variables
        gar_location = os.environ["GAR_LOCATION"]
        project_id = os.environ["GCP_PROJECT_ID"]
        repo_name = os.environ["GAR_REPOSITORY"]
        
        # Create Artifact Registry repository if it doesn't exist
        self.create_artifact_registry_repository(project_id, gar_location, repo_name)
        
        # Configure Docker for GAR
        self.configure_docker_for_gar(gar_location)
        
        # Build image
        image_tag = f"{gar_location}-docker.pkg.dev/{project_id}/{repo_name}/{os.environ['IMAGE_NAME']}:{os.environ['IMAGE_TAG']}"
        
        self.build_image(image_tag)
        self.push_image(image_tag)
        
        self.logger.info("Docker image build and push completed successfully.")
        return image_tag
