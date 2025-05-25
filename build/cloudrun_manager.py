"""
Google Cloud Run deployment manager
"""
import subprocess
import sys
import logging
from typing import Any


class CloudRunManager:
    """Manages Cloud Run service deployment"""
    
    def __init__(self, logger: logging.Logger, gcloud_path: str, config: dict[str, Any]):
        self.logger = logger
        self.gcloud_path = gcloud_path
        self.config = config
    
    def run_command(self, command: list[str], check: bool = True, capture_output: bool = False) -> Any:
        """Run a shell command"""
        try:
            self.logger.debug(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error: {e}")
            if check:
                sys.exit(1)
            raise
    
    def enable_cloud_run_api(self):
        """Enable Cloud Run API if not already enabled"""
        project_id = self.config.get("gcp", {}).get("project_id")
        if not project_id:
            self.logger.error("GCP project ID not found in configuration")
            sys.exit(1)
            
        self.logger.info("Checking if Cloud Run API is enabled...")
        
        try:
            # Check if Cloud Run API is enabled
            result = self.run_command([
                self.gcloud_path, "services", "list", 
                "--enabled", "--filter=name:run.googleapis.com",
                "--project", project_id
            ], capture_output=True)
            
            if "run.googleapis.com" in result.stdout:
                self.logger.info("Cloud Run API is already enabled")
                return
                
        except subprocess.CalledProcessError:
            pass
            
        self.logger.info("Enabling Cloud Run API...")
        try:
            self.run_command([
                self.gcloud_path, "services", "enable", "run.googleapis.com",
                "--project", project_id
            ])
            self.logger.info("Cloud Run API enabled successfully")
            
            # Wait a moment for the API to be fully available
            import time
            time.sleep(10)
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to enable Cloud Run API: {e}")
            sys.exit(1)
    
    def deploy_to_cloudrun(self, image_url: str, service_name: str = "discord-epistulus-service"):
        """Deploy the Docker image to Cloud Run"""
        self.logger.info(f"Deploying {service_name} to Cloud Run...")
        
        # Enable Cloud Run API first
        self.enable_cloud_run_api()
        
        region = self.config.get("gcp", {}).get("region", "asia-northeast3")
        project_id = self.config.get("gcp", {}).get("project_id")
        
        if not project_id:
            self.logger.error("GCP project ID not found in configuration")
            sys.exit(1)
        
        # Get Discord token from config
        discord_token = self.config.get("discord", {}).get("token", "")
        if not discord_token or discord_token == "YOUR_DISCORD_TOKEN_HERE":
            self.logger.warning("Discord token not configured in build_config.json")
            self.logger.warning("Please set your Discord bot token in the 'discord.token' field")
            self.logger.warning("For now, deploying without Discord token (service will fail to start)")
            discord_token = "PLACEHOLDER_TOKEN"
        
        deploy_command = [
            self.gcloud_path, "run", "deploy", service_name,
            "--image", image_url,
            "--region", region,
            "--platform", "managed",
            "--project", project_id,
            "--allow-unauthenticated",  # Discord bot doesn't need authentication
            "--port", "8080",  # Default port for Cloud Run
            "--memory", "512Mi",  # Reasonable memory for a Discord bot
            "--cpu", "1",  # Single CPU should be enough
            "--concurrency", "80",  # Default concurrency
            "--timeout", "300",  # 5 minute timeout
            "--set-env-vars", f"DISCORD_TOKEN={discord_token}"  # Add environment variables (PORT is automatically set by Cloud Run)
        ]
        
        try:
            self.run_command(deploy_command)
            self.logger.info("Cloud Run deployment completed successfully!")
            return f"https://{service_name}-{region}-{project_id}.a.run.app"
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Cloud Run deployment failed: {e}")
            # Try to get more detailed error information
            self.logger.error("Checking Cloud Run API status...")
            try:
                status_result = self.run_command([
                    self.gcloud_path, "run", "services", "list", 
                    "--region", region, "--project", project_id
                ], capture_output=True)
                self.logger.info(f"Available services: {status_result.stdout}")
            except:
                pass
            sys.exit(1)
    
    def check_service_status(self, service_name: str = "discord-epistulus-service"):
        """Check the status of the Cloud Run service"""
        region = self.config.get("gcp", {}).get("region", "asia-northeast3")
        project_id = self.config.get("gcp", {}).get("project_id")
        
        status_command = [
            self.gcloud_path, "run", "services", "describe", service_name,
            "--region", region,
            "--project", project_id,
            "--format", "value(status.url)"
        ]
        
        try:
            result = self.run_command(status_command, capture_output=True)
            if result.stdout.strip():
                self.logger.info(f"Service is running at: {result.stdout.strip()}")
                return result.stdout.strip()
            return None
        except subprocess.CalledProcessError:
            self.logger.warning("Could not get service status (service might not exist yet)")
            return None
