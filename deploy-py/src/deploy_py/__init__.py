from .project_detector import ProjectDetector
from .github_secrets import GitHubSecretsManager
from .gcp_manager import GCPDeploymentManager
from .interactive_setup import InteractiveSetup
from .config_manager import ConfigManager
from .gcloud_manager import GCloudManager

def main() -> None:
    print("Hello from deploy-py!")

__all__ = ["ProjectDetector", "GitHubSecretsManager", "GCPDeploymentManager", "InteractiveSetup", "ConfigManager", "GCloudManager"]
