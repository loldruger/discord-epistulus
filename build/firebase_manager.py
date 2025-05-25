"""
Firebase deployment manager
"""
import subprocess
import sys
import logging
import shutil
from pathlib import Path
from typing import Any


class FirebaseManager:
    """Manages Firebase deployment"""
    
    def __init__(self, logger: logging.Logger, project_root: Path):
        self.logger = logger
        self.project_root = project_root
    
    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        return shutil.which(command) is not None
    
    def run_command(self, command: list[str], check: bool = True, capture_output: bool = False) -> Any:
        """Run a shell command"""
        try:
            self.logger.debug(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True,
                cwd=self.project_root
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error: {e}")
            if check:
                sys.exit(1)
            raise
    
    def check_firebase_cli(self):
        """Check if Firebase CLI is installed"""
        if not self.check_command_exists("firebase"):
            self.logger.error("Firebase CLI is not installed.")
            self.logger.error("Please install Firebase CLI: npm install -g firebase-tools")
            self.logger.error("Or visit: https://firebase.google.com/docs/cli#install_the_firebase_cli")
            sys.exit(1)
        self.logger.info("Firebase CLI check: OK")
    
    def check_firebase_config(self):
        """Check if Firebase is properly configured"""
        firebase_json = self.project_root / "firebase.json"
        if not firebase_json.exists():
            self.logger.error("firebase.json not found. Please run 'firebase init' first.")
            sys.exit(1)
        
        firebaserc = self.project_root / ".firebaserc"
        if not firebaserc.exists():
            self.logger.warning(".firebaserc not found. Firebase project might not be configured.")
        
        self.logger.info("Firebase configuration check: OK")
    
    def login_firebase(self):
        """Ensure Firebase is logged in"""
        try:
            # Check if already logged in
            self.run_command(["firebase", "projects:list"], capture_output=True)
            self.logger.info("Firebase authentication check: OK")
        except subprocess.CalledProcessError:
            self.logger.info("Firebase login required...")
            try:
                self.run_command(["firebase", "login", "--no-localhost"])
                self.logger.info("Firebase login completed")
            except subprocess.CalledProcessError:
                self.logger.error("Firebase login failed")
                sys.exit(1)
    
    def deploy_firebase(self):
        """Deploy to Firebase"""
        self.logger.info("Starting Firebase deployment...")
        
        try:
            result = self.run_command(["firebase", "deploy"], capture_output=True)
            self.logger.info("Firebase deployment completed successfully!")
            
            # Extract the hosting URL from the output
            if result.stdout:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Hosting URL:' in line:
                        url = line.split('Hosting URL:')[1].strip()
                        self.logger.info(f"Your application is live at: {url}")
                        return url
            
            return None
            
        except subprocess.CalledProcessError:
            self.logger.error("Firebase deployment failed")
            sys.exit(1)
    
    def run_full_deployment(self):
        """Run complete Firebase deployment process"""
        self.check_firebase_cli()
        self.check_firebase_config()
        self.login_firebase()
        return self.deploy_firebase()
