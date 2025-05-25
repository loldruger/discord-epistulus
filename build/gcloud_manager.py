"""
Google Cloud CLI management module
"""
import subprocess
import sys
import shutil
import logging
from pathlib import Path
from typing import Any

try:
    import importlib.util
    
    # Load gcloud_installation module dynamically
    gcloud_install_spec = importlib.util.spec_from_file_location(
        "gcloud_installation", 
        Path(__file__).parent / "gcloud_installation.py"
    )
    if gcloud_install_spec and gcloud_install_spec.loader:
        gcloud_install_module = importlib.util.module_from_spec(gcloud_install_spec)
        gcloud_install_spec.loader.exec_module(gcloud_install_module)
        install_gcloud = gcloud_install_module.install_gcloud
    else:
        install_gcloud = None
    
    # Load gcloud_reinit module dynamically
    gcloud_reinit_spec = importlib.util.spec_from_file_location(
        "gcloud_reinit", 
        Path(__file__).parent / "gcloud_reinit.py"
    )
    if gcloud_reinit_spec and gcloud_reinit_spec.loader:
        gcloud_reinit_module = importlib.util.module_from_spec(gcloud_reinit_spec)
        gcloud_reinit_spec.loader.exec_module(gcloud_reinit_module)
        reset_gcloud_config = gcloud_reinit_module.reset_gcloud_config
    else:
        reset_gcloud_config = None
        
except Exception as e:
    print(f"Warning: Could not import gcloud modules: {e}")
    install_gcloud = None
    reset_gcloud_config = None


class GCloudManager:
    """Manages Google Cloud CLI installation, configuration, and authentication"""
    
    def __init__(self, logger: logging.Logger, config: dict[str, Any]):
        self.logger = logger
        self.config = config
        self.gcloud_path: str | None = None
    
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
    
    def find_gcloud_in_path(self) -> bool:
        """Try to find gcloud in PATH"""
        gcloud_path = shutil.which("gcloud")
        if gcloud_path:
            self.gcloud_path = gcloud_path
            self.logger.info(f"gcloud: Found in PATH at {self.gcloud_path}")
            return True
        return False
    
    def find_gcloud_in_common_dir(self, common_dir: Path) -> bool:
        """Try to find gcloud in common installation directory"""
        gcloud_executable = common_dir / "gcloud"
        if gcloud_executable.exists() and gcloud_executable.is_file():
            self.gcloud_path = str(gcloud_executable)
            self.logger.info(f"gcloud: Found in common directory at {self.gcloud_path}")
            return True
        return False
    
    def source_gcloud_config(self) -> bool:
        """Source gcloud configuration files"""
        home = Path.home()
        
        path_file = home / "google-cloud-sdk" / "path.bash.inc"
        completion_file = home / "google-cloud-sdk" / "completion.bash.inc"
        
        if path_file.exists():
            self.logger.info(f"Found gcloud path config: {path_file}")
            return True
        elif completion_file.exists():
            self.logger.info(f"Found gcloud completion config: {completion_file}")
            return True
            
        return False
    
    def install_and_setup_gcloud(self, common_dir: Path):
        """Install gcloud and setup path"""
        self.logger.info("gcloud: Not found. Attempting installation...")
        
        # Use the modularized installation function
        if install_gcloud and install_gcloud():
            self.logger.info("gcloud CLI installation completed.")
        else:
            # Fallback to original script method if module not available
            self.logger.warning("Using fallback installation method...")
            if "scripts" in self.config and "gcloud_installation" in self.config["scripts"]:
                installation_script = Path(self.config["scripts"]["gcloud_installation"])
                if installation_script.exists():
                    installation_script.chmod(0o755)
                    
                    try:
                        self.run_command(["python3", str(installation_script)])
                        self.logger.info("gcloud CLI installation script finished.")
                    except subprocess.CalledProcessError:
                        self.logger.error("gcloud CLI installation script failed. Please install gcloud manually. (https://cloud.google.com/sdk/docs/install)")
                        sys.exit(1)
                else:
                    self.logger.error("Fallback installation script not found. Please install gcloud manually. (https://cloud.google.com/sdk/docs/install)")
                    sys.exit(1)
            else:
                self.logger.error("No installation method available. Please install gcloud manually. (https://cloud.google.com/sdk/docs/install)")
                sys.exit(1)
            
        # Try to find gcloud after installation
        self.source_gcloud_config()
        
        if self.find_gcloud_in_path():
            self.logger.info("gcloud: Now found in PATH after installation.")
            return
            
        if self.find_gcloud_in_common_dir(common_dir):
            self.logger.info("gcloud: Found in common directory after installation.")
            return
            
        self.logger.error("gcloud installation was attempted, but the command is still not found. Please check the installation output or manually set up your PATH.")
        sys.exit(1)
    
    def setup_gcloud(self):
        """Detect, install, and configure gcloud CLI"""
        self.logger.info("Checking for gcloud CLI...")
        
        common_gcloud_install_dir = Path.home() / "google-cloud-sdk" / "bin"
        
        # Try finding gcloud in PATH first
        if self.find_gcloud_in_path():
            return
        elif self.find_gcloud_in_common_dir(common_gcloud_install_dir):
            return
        else:
            self.install_and_setup_gcloud(common_gcloud_install_dir)
            
        # Final verification
        if not self.gcloud_path:
            self.logger.error("gcloud CLI not found even after installation attempt. Please install manually.")
            sys.exit(1)
            
        self.logger.info(f"gcloud CLI check: OK. Path: {self.gcloud_path}")
    
    def ask_user_confirmation(self, prompt: str) -> bool:
        """Ask user for yes/no confirmation"""
        while True:
            response = input(f"{prompt} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'")
    
    def check_gcloud_auth(self) -> bool:
        """Check if gcloud is already authenticated"""
        if not self.gcloud_path:
            return False
            
        try:
            result = self.run_command([str(self.gcloud_path), "auth", "list", "--format=value(account)"], capture_output=True)
            if result.stdout.strip():
                self.logger.info(f"gcloud already authenticated as: {result.stdout.strip()}")
                return True
            return False
        except subprocess.CalledProcessError:
            return False
    
    def authenticate_gcloud(self):
        """Handle gcloud authentication and initialization"""
        # Check if already authenticated
        if self.check_gcloud_auth():
            if not self.ask_user_confirmation("gcloud is already authenticated. Do you want to re-authenticate?"):
                self.logger.info("Skipping gcloud authentication.")
                return
        
        # Ask user if they want to re-initialize gcloud configuration
        if self.ask_user_confirmation("Do you want to reset your current gcloud configuration before proceeding?"):
            self.logger.info("Running gcloud configuration reset...")
            
            # Use the modularized reset function
            if reset_gcloud_config and reset_gcloud_config():
                self.logger.info("gcloud configuration reset completed.")
            else:
                # Fallback to script method if module not available
                self.logger.warning("Using fallback reset method...")
                if "scripts" in self.config and "gcloud_reinit" in self.config["scripts"]:
                    reinit_script = self.config["scripts"]["gcloud_reinit"]
                    reinit_script_path = Path(reinit_script)
                    if reinit_script_path.exists():
                        try:
                            self.run_command(["python3", reinit_script])
                            self.logger.info("gcloud configuration reset script finished.")
                        except subprocess.CalledProcessError:
                            self.logger.error("gcloud configuration reset script failed.")
                            sys.exit(1)
                    else:
                        self.logger.warning("Fallback reset script not found. Skipping reset.")
                else:
                    self.logger.warning("No reset method available. Skipping reset.")
        else:
            self.logger.info("Skipping gcloud configuration reset.")
            
        self.logger.info("Proceeding with gcloud initialization and authentication.")
        
        # Ensure gcloud_path is not None
        if not self.gcloud_path:
            self.logger.error("gcloud path is not set. Cannot proceed with authentication.")
            sys.exit(1)
        
        # Check if we need to run gcloud init
        try:
            # Check if project is already set
            result = self.run_command([str(self.gcloud_path), "config", "get-value", "project"], capture_output=True)
            if result.stdout.strip():
                self.logger.info(f"gcloud project already set: {result.stdout.strip()}")
            else:
                self.logger.info("Running gcloud init...")
                self.run_command([str(self.gcloud_path), "init", "--skip-diagnostics", "--no-launch-browser"])
        except subprocess.CalledProcessError:
            self.logger.info("Running gcloud init...")
            self.run_command([str(self.gcloud_path), "init", "--skip-diagnostics", "--no-launch-browser"])
        
        # Check authentication again after init
        if not self.check_gcloud_auth():
            self.logger.info("Authentication required...")
            try:
                self.run_command([str(self.gcloud_path), "auth", "login", "--no-browser"])
            except subprocess.CalledProcessError:
                self.logger.warning("Regular auth login failed, trying alternative method...")
                self.logger.info("Please authenticate manually by running: gcloud auth login")
                input("Press Enter after you have completed authentication...")
        
        # Application default credentials (optional, skip if fails)
        try:
            self.run_command([str(self.gcloud_path), "auth", "application-default", "login", "--no-launch-browser"])
        except subprocess.CalledProcessError:
            self.logger.warning("Application default credentials setup failed. This is optional and can be set up later if needed.")
    
    def get_gcloud_path(self) -> str | None:
        """Get the gcloud executable path"""
        return self.gcloud_path
