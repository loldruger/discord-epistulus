"""
Google Cloud Workload Identity Federation Manager for GitHub Actions
Automates the setup of Workload Identity Federation for secure GitHub Actions deployment
"""
import subprocess
import sys
import logging
import json
from typing import Any


class WorkloadIdentityManager:
    """Manages Workload Identity Federation setup for GitHub Actions"""
    
    def __init__(self, logger: logging.Logger, gcloud_path: str, config: dict[str, Any]):
        self.logger = logger
        self.gcloud_path = gcloud_path
        self.config = config
        self.project_id = config.get("gcp", {}).get("project_id")
        self.pool_id = "github-actions-pool"
        self.provider_id = "github-actions-provider"
        self.service_account = "github-actions-sa"
        
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
            if capture_output and e.stdout:
                self.logger.error(f"Stdout: {e.stdout}")
            if capture_output and e.stderr:
                self.logger.error(f"Stderr: {e.stderr}")
            if check:
                raise
            return None
    
    def enable_required_apis(self):
        """Enable required APIs for Workload Identity Federation"""
        self.logger.info("Enabling required APIs...")
        
        required_apis = [
            "iam.googleapis.com",
            "iamcredentials.googleapis.com", 
            "sts.googleapis.com",
            "cloudresourcemanager.googleapis.com"
        ]
        
        for api in required_apis:
            self.logger.info(f"Enabling {api}...")
            try:
                self.run_command([
                    self.gcloud_path, "services", "enable", api,
                    "--project", self.project_id
                ])
                self.logger.info(f"✅ {api} enabled")
            except subprocess.CalledProcessError:
                self.logger.warning(f"Failed to enable {api} - it might already be enabled")
        
        # Wait for APIs to be fully available
        import time
        self.logger.info("Waiting for APIs to be fully available...")
        time.sleep(10)
    
    def create_service_account(self):
        """Create a service account for GitHub Actions"""
        self.logger.info(f"Creating service account: {self.service_account}")
        
        # Check if service account already exists
        try:
            result = self.run_command([
                self.gcloud_path, "iam", "service-accounts", "describe",
                f"{self.service_account}@{self.project_id}.iam.gserviceaccount.com",
                "--project", self.project_id
            ], capture_output=True, check=False)
            
            if result and result.returncode == 0:
                self.logger.info("✅ Service account already exists")
                return
                
        except subprocess.CalledProcessError:
            pass
        
        # Create service account
        try:
            self.run_command([
                self.gcloud_path, "iam", "service-accounts", "create", self.service_account,
                "--display-name", "GitHub Actions Service Account",
                "--description", "Service account for GitHub Actions CI/CD",
                "--project", self.project_id
            ])
            self.logger.info("✅ Service account created successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create service account: {e}")
            raise
    
    def grant_service_account_permissions(self):
        """Grant necessary permissions to the service account"""
        self.logger.info("Granting permissions to service account...")
        
        sa_email = f"{self.service_account}@{self.project_id}.iam.gserviceaccount.com"
        
        required_roles = [
            "roles/run.admin",  # Cloud Run admin
            "roles/artifactregistry.admin",  # Artifact Registry admin
            "roles/iam.serviceAccountUser",  # Service Account User
            "roles/storage.admin",  # Storage admin (for artifacts)
        ]
        
        for role in required_roles:
            self.logger.info(f"Granting {role}...")
            try:
                self.run_command([
                    self.gcloud_path, "projects", "add-iam-policy-binding", self.project_id,
                    "--member", f"serviceAccount:{sa_email}",
                    "--role", role
                ])
                self.logger.info(f"✅ {role} granted")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to grant {role}: {e}")
    
    def create_workload_identity_pool(self):
        """Create Workload Identity Pool"""
        self.logger.info(f"Creating Workload Identity Pool: {self.pool_id}")
        
        # Check if pool already exists
        try:
            result = self.run_command([
                self.gcloud_path, "iam", "workload-identity-pools", "describe", self.pool_id,
                "--location", "global",
                "--project", self.project_id
            ], capture_output=True, check=False)
            
            if result and result.returncode == 0:
                self.logger.info("✅ Workload Identity Pool already exists")
                return
                
        except subprocess.CalledProcessError:
            pass
        
        # Create pool
        try:
            self.run_command([
                self.gcloud_path, "iam", "workload-identity-pools", "create", self.pool_id,
                "--location", "global",
                "--display-name", "GitHub Actions Pool",
                "--description", "Workload Identity Pool for GitHub Actions",
                "--project", self.project_id
            ])
            self.logger.info("✅ Workload Identity Pool created successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create Workload Identity Pool: {e}")
            raise
    
    def create_workload_identity_provider(self, github_repo: str):
        """Create Workload Identity Provider for GitHub"""
        self.logger.info(f"Creating Workload Identity Provider: {self.provider_id}")
        
        # Check if provider already exists
        try:
            result = self.run_command([
                self.gcloud_path, "iam", "workload-identity-pools", "providers", "describe", self.provider_id,
                "--workload-identity-pool", self.pool_id,
                "--location", "global",
                "--project", self.project_id
            ], capture_output=True, check=False)
            
            if result and result.returncode == 0:
                self.logger.info("✅ Workload Identity Provider already exists")
                return
                
        except subprocess.CalledProcessError:
            pass
        
        # Create provider
        try:
            attribute_mapping = {
                "google.subject": "assertion.sub",
                "attribute.actor": "assertion.actor",
                "attribute.repository": "assertion.repository"
            }
            
            attribute_condition = f'assertion.repository=="{github_repo}"'
            
            self.run_command([
                self.gcloud_path, "iam", "workload-identity-pools", "providers", "create-oidc", self.provider_id,
                "--workload-identity-pool", self.pool_id,
                "--location", "global",
                "--issuer-uri", "https://token.actions.githubusercontent.com",
                "--attribute-mapping", ",".join([f"{k}={v}" for k, v in attribute_mapping.items()]),
                "--attribute-condition", attribute_condition,
                "--display-name", "GitHub Actions Provider",
                "--project", self.project_id
            ])
            self.logger.info("✅ Workload Identity Provider created successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create Workload Identity Provider: {e}")
            raise
    
    def bind_service_account_to_pool(self, github_repo: str):
        """Bind service account to Workload Identity Pool"""
        self.logger.info("Binding service account to Workload Identity Pool...")
        
        project_number = self.get_project_number()
        sa_email = f"{self.service_account}@{self.project_id}.iam.gserviceaccount.com"
        pool_member = f"principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{self.pool_id}/attribute.repository/{github_repo}"
        
        try:
            self.run_command([
                self.gcloud_path, "iam", "service-accounts", "add-iam-policy-binding", sa_email,
                "--role", "roles/iam.workloadIdentityUser",
                "--member", pool_member,
                "--project", self.project_id
            ])
            self.logger.info("✅ Service account bound to Workload Identity Pool")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to bind service account: {e}")
            raise
    
    def clean_deleted_pools(self):
        """Clean up deleted workload identity pools completely"""
        self.logger.info("Checking for deleted workload identity pools...")
        
        try:
            # List all pools including deleted ones
            result = self.run_command([
                self.gcloud_path, "iam", "workload-identity-pools", "list",
                "--location=global", "--show-deleted", "--format=json",
                "--project", self.project_id
            ], capture_output=True)
            
            if not result or not result.stdout:
                self.logger.info("No pools found")
                return
            
            pools = json.loads(result.stdout)
            deleted_pools = [pool for pool in pools if pool.get("state") == "DELETED"]
            
            if not deleted_pools:
                self.logger.info("✅ No deleted pools to clean up")
                return
            
            self.logger.info(f"Found {len(deleted_pools)} deleted pools to purge")
            
            for pool in deleted_pools:
                pool_name = pool["name"].split("/")[-1]
                self.logger.info(f"Purging deleted pool: {pool_name}")
                
                try:
                    # First undelete the pool
                    self.run_command([
                        self.gcloud_path, "iam", "workload-identity-pools", "undelete",
                        pool_name, "--location=global", "--project", self.project_id,
                        "--quiet"
                    ])
                    
                    # Wait a moment
                    import time
                    time.sleep(2)
                    
                    # Then delete it permanently
                    self.run_command([
                        self.gcloud_path, "iam", "workload-identity-pools", "delete",
                        pool_name, "--location=global", "--project", self.project_id,
                        "--quiet"
                    ])
                    
                    self.logger.info(f"✅ Successfully purged pool: {pool_name}")
                    
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"⚠️ Failed to purge pool {pool_name}: {e}")
                    continue
            
        except Exception as e:
            self.logger.warning(f"Error during pool cleanup: {e}")

    def get_provider_name(self) -> str:
        """Get the full provider name"""
        project_number = self.get_project_number()
        return f"projects/{project_number}/locations/global/workloadIdentityPools/{self.pool_id}/providers/{self.provider_id}"
    
    def get_service_account_email(self) -> str:
        """Get the service account email"""
        return f"{self.service_account}@{self.project_id}.iam.gserviceaccount.com"
    
    def get_project_number(self) -> str:
        """Get the project number (required for Workload Identity binding)"""
        try:
            result = self.run_command([
                self.gcloud_path, "projects", "describe", self.project_id,
                "--format=value(projectNumber)"
            ], capture_output=True)
            
            if result and result.stdout:
                return result.stdout.strip()
            else:
                self.logger.error("Failed to get project number")
                raise ValueError("Could not retrieve project number")
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get project number: {e}")
            raise
    
    def setup_workload_identity_federation(self, github_repo: str):
        """Complete setup of Workload Identity Federation"""
        self.logger.info("🚀 Starting Workload Identity Federation setup...")
        
        if not self.project_id:
            self.logger.error("GCP project ID not found in configuration")
            sys.exit(1)
        
        if not github_repo:
            self.logger.error("GitHub repository not specified")
            sys.exit(1)
        
        try:
            # Step 0: Clean up deleted pools first
            self.clean_deleted_pools()
            
            # Step 1: Enable required APIs
            self.enable_required_apis()
            
            # Step 2: Create service account
            self.create_service_account()
            
            # Step 3: Grant permissions to service account
            self.grant_service_account_permissions()
            
            # Step 4: Create Workload Identity Pool
            self.create_workload_identity_pool()
            
            # Step 5: Create Workload Identity Provider
            self.create_workload_identity_provider(github_repo)
            
            # Step 6: Bind service account to pool
            self.bind_service_account_to_pool(github_repo)
            
            # Step 7: Output configuration for GitHub Secrets
            self.output_github_secrets_config()
            
            self.logger.info("🎉 Workload Identity Federation setup completed successfully!")
            
        except Exception as e:
            self.logger.error(f"❌ Workload Identity Federation setup failed: {e}")
            sys.exit(1)
    
    def output_github_secrets_config(self):
        """Output the configuration needed for GitHub Secrets"""
        self.logger.info("\n" + "="*60)
        self.logger.info("📋 GitHub Secrets Configuration")
        self.logger.info("="*60)
        
        provider_name = self.get_provider_name()
        sa_email = self.get_service_account_email()
        
        secrets_config = {
            "WIF_PROVIDER": provider_name,
            "WIF_SERVICE_ACCOUNT": sa_email,
            "GCP_PROJECT_ID": self.project_id,
            "GAR_LOCATION": self.config.get("gcp", {}).get("region", "asia-northeast3"),
            "GAR_REPOSITORY": "discord-epistulus-repo",
            "SERVICE_NAME": "discord-epistulus-service"
        }
        
        self.logger.info("\nAdd these secrets to your GitHub repository:")
        self.logger.info("Settings → Secrets and variables → Actions → New repository secret")
        self.logger.info("\n")
        
        for key, value in secrets_config.items():
            self.logger.info(f"{key}: {value}")
        
        self.logger.info("\n" + "="*60)
        self.logger.info("✅ Configuration complete!")
        self.logger.info("="*60)
        
        return secrets_config


def main():
    """Main function for testing"""
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Example configuration
    config = {
        "gcp": {
            "project_id": "epistulus",
            "region": "asia-northeast3"
        }
    }
    
    gcloud_path = "/home/loldruger/google-cloud-sdk/bin/gcloud"
    github_repo = "loldruger/discord-epistulus"  # Replace with actual repo
    
    wif_manager = WorkloadIdentityManager(logger, gcloud_path, config)
    wif_manager.setup_workload_identity_federation(github_repo)


if __name__ == "__main__":
    main()
