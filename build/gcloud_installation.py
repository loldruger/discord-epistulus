import subprocess
import platform
import os
import shutil

def is_gcloud_installed():
    # Check if gcloud is installed
    try:
        # Use shutil.which to find the gcloud executable
        # This is a more reliable way to check if a command is in PATH
        if shutil.which("gcloud"):
            subprocess.run(["gcloud", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_os_type():
    # Detect OS type
    system = platform.system()
    if system == "Linux":
        return "linux"
    elif system == "Darwin": # Darwin is the system name for macOS
        return "macos"
    else:
        return "unknown"

def install_gcloud_linux():
    # Install gcloud CLI on Linux
    print("Attempting to install Google Cloud SDK on Linux...")
    try:
        # Check for sudo privileges first
        if os.geteuid() != 0:
            print("This script needs sudo privileges to install packages. Please run as root or with sudo.")
            # Try to re-run with sudo if not already sudo
            # This is a bit risky and might not work in all environments or if sudo requires a password interactively.
            # A better approach is to instruct the user to run with sudo.
            # For now, we will proceed assuming the user will handle sudo if needed by the package manager.

        # Debian/Ubuntu
        if os.path.exists("/etc/debian_version"):
            print("Detected Debian/Ubuntu based system.")
            print("Updating package lists...")
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            print("Installing prerequisites...")
            subprocess.run(["sudo", "apt-get", "install", "-y", "apt-transport-https", "ca-certificates", "gnupg", "curl"], check=True)
            
            print("Adding Google Cloud SDK package source...")
            keyring_dir = "/usr/share/keyrings"
            keyring_path = os.path.join(keyring_dir, "cloud.google.gpg")
            sources_list_path = "/etc/apt/sources.list.d/google-cloud-sdk.list"

            # Ensure the keyring directory exists
            subprocess.run(["sudo", "mkdir", "-p", keyring_dir], check=True)
            
            # Download and add the public key
            print(f"Downloading Google Cloud public key to {keyring_path}...")
            curl_gpg_command = f"curl -sSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o {keyring_path}"
            subprocess.run(curl_gpg_command, shell=True, check=True)
            
            # Add the SDK repository
            print(f"Adding repository to {sources_list_path}...")
            repo_entry = f"deb [signed-by={keyring_path}] https://packages.cloud.google.com/apt cloud-sdk main"
            echo_tee_command = f"echo '{repo_entry}' | sudo tee {sources_list_path}"
            subprocess.run(echo_tee_command, shell=True, check=True)
            
            print("Updating package lists again after adding new repository...")
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            print("Installing google-cloud-cli...")
            subprocess.run(["sudo", "apt-get", "install", "-y", "google-cloud-cli"], check=True)

        # Red Hat/Fedora/CentOS
        elif os.path.exists("/etc/redhat-release"):
            print("Detected Red Hat/Fedora/CentOS based system.")
            repo_file_path = "/etc/yum.repos.d/google-cloud-sdk.repo"
            repo_content = """[google-cloud-sdk]
name=Google Cloud SDK
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el8-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg
       https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg"""
            
            print(f"Creating repository file at {repo_file_path}...")
            # Write to a temporary file first, then move with sudo to handle permissions
            temp_repo_path = "/tmp/google-cloud-sdk.repo"
            with open(temp_repo_path, "w") as f:
                f.write(repo_content)
            subprocess.run(["sudo", "mv", temp_repo_path, repo_file_path], check=True)
            
            # Determine package manager (dnf or yum)
            pkg_manager = None
            if shutil.which("dnf"):
                pkg_manager = "dnf"
            elif shutil.which("yum"):
                pkg_manager = "yum"
            
            if pkg_manager:
                print(f"Installing google-cloud-cli using {pkg_manager}...")
                subprocess.run(["sudo", pkg_manager, "install", "-y", "google-cloud-cli"], check=True)
            else:
                print("Could not find dnf or yum. Please install Google Cloud SDK manually.")
                return False
        else:
            print("Unsupported Linux distribution. Please install Google Cloud SDK manually from https://cloud.google.com/sdk/docs/install")
            return False
        print("Google Cloud SDK installed successfully on Linux.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing Google Cloud SDK on Linux: {e}")
        if hasattr(e, 'stdout') and e.stdout:
            print(f"Stdout: {e.stdout.decode(errors='ignore')}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Stderr: {e.stderr.decode(errors='ignore')}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during Linux installation: {e}")
        return False

def install_gcloud_macos():
    # Install gcloud CLI on macOS
    print("Attempting to install Google Cloud SDK on macOS...")
    temp_download_dir: str | None = None
    try:
        arch = platform.machine() # e.g., 'x86_64' or 'arm64'
        sdk_url = None
        if arch == "arm64": # Apple Silicon
            sdk_url = "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-mac-arm.tar.gz"
        elif arch == "x86_64": # Intel
            sdk_url = "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-mac-x86_64.tar.gz"
        else:
            print(f"Unsupported macOS architecture: {arch}. Please install manually from https://cloud.google.com/sdk/docs/install")
            return False

        # Define paths for download and extraction
        # User's home directory is a common place for such installations if not system-wide
        home_dir = os.path.expanduser("~")
        gcloud_sdk_base_dir = os.path.join(home_dir, "google-cloud-sdk") # Default install dir for the script
        temp_download_dir = "/tmp/gcloud_sdk_download"
        os.makedirs(temp_download_dir, exist_ok=True)
        
        file_name = sdk_url.split("/")[-1]
        download_path = os.path.join(temp_download_dir, file_name)

        print(f"Downloading {sdk_url} to {download_path}...")
        subprocess.run(["curl", "-L", "-o", download_path, sdk_url], check=True)
        
        print(f"Extracting {download_path} to {temp_download_dir}...")
        # Extract directly into the temp_download_dir, the tarball usually has a `google-cloud-sdk` top folder
        subprocess.run(["tar", "-xf", download_path, "-C", temp_download_dir], check=True)
        
        # The extracted folder is typically named 'google-cloud-sdk'
        extracted_sdk_path = os.path.join(temp_download_dir, "google-cloud-sdk")
        if not os.path.isdir(extracted_sdk_path):
            # Fallback: list contents if the name is different (unlikely for official archives)
            found_dirs = [d for d in os.listdir(temp_download_dir) if os.path.isdir(os.path.join(temp_download_dir, d)) and d.startswith("google-cloud-sdk")]
            if not found_dirs:
                 print(f"Could not find 'google-cloud-sdk' directory in the extracted archive at {temp_download_dir}.")
                 shutil.rmtree(temp_download_dir)
                 return False
            extracted_sdk_path = os.path.join(temp_download_dir, found_dirs[0])

        install_script_path = os.path.join(extracted_sdk_path, "install.sh")
        print(f"Running install script: {install_script_path}")
        # The install.sh script by default installs to a directory named google-cloud-sdk in the user's home directory
        # or the directory containing the script if it's not in home.
        # We will run it with flags for non-interactive setup.
        # --path-update=true: attempts to update shell profile (e.g., .bash_profile, .zshrc)
        # --usage-reporting=false: disables usage reporting
        # --quiet: suppresses prompts
        # We can also specify --install-dir <path> if we want to control the final location, 
        # but the default behavior of placing it in ~/google-cloud-sdk is often fine.
        install_command = [install_script_path, "--quiet", "--usage-reporting=false", "--path-update=true"]
        
        print(f"Executing: {' '.join(install_command)}")
        # The install script handles moving itself to the final location (usually ~/google-cloud-sdk)
        subprocess.run(install_command, check=True, cwd=extracted_sdk_path) # Run from within the extracted dir
        
        print("Google Cloud SDK installation script executed.")
        print(f"The SDK should be installed in a directory like '{gcloud_sdk_base_dir}' (or where the script placed it).")
        print("Please open a new terminal session or source your shell profile (e.g., `source ~/.bash_profile`, `source ~/.zshrc`, or `source ~/.profile`) for changes to take effect.")
        print("After that, run `gcloud init` to initialize the SDK.")
        
        # Clean up the temporary download directory
        print(f"Cleaning up temporary directory: {temp_download_dir}")
        shutil.rmtree(temp_download_dir)
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error installing Google Cloud SDK on macOS: {e}")
        if hasattr(e, 'stdout') and e.stdout:
            print(f"Stdout: {e.stdout.decode(errors='ignore')}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Stderr: {e.stderr.decode(errors='ignore')}")
        if temp_download_dir is not None and os.path.exists(temp_download_dir):
            shutil.rmtree(temp_download_dir)
        return False
    except Exception as e:
        print(f"An unexpected error occurred during macOS installation: {e}")
        if temp_download_dir is not None and os.path.exists(temp_download_dir):
            shutil.rmtree(temp_download_dir)
        return False

def install_gcloud():
    """Main function to install gcloud CLI if not already installed"""
    if is_gcloud_installed():
        print("Google Cloud SDK is already installed.")
        return True
    
    print("Google Cloud SDK not found. Attempting to install...")
    os_type = get_os_type()
    success = False
    
    if os_type == "linux":
        success = install_gcloud_linux()
    elif os_type == "macos":
        success = install_gcloud_macos()
    else:
        current_os = platform.system()
        if current_os == "Windows":
            print("Windows is not supported by this script. Please install Google Cloud SDK manually from https://cloud.google.com/sdk/docs/install")
        else:
            print(f"Unsupported operating system: {current_os}. Please install Google Cloud SDK manually from https://cloud.google.com/sdk/docs/install")
        return False

    if success:
        print("Installation process finished.")
        print("Please open a new terminal or source your shell profile, then run 'gcloud --version' to verify.")
        print("You may also need to run 'gcloud init' to initialize the SDK.")
        return True
    elif os_type in ["linux", "macos"]:
        print("Google Cloud SDK installation failed. Please check the messages above and try manual installation from https://cloud.google.com/sdk/docs/install")
        return False
    
    return False


if __name__ == "__main__":
    # This allows the script to still be run standalone for testing
    install_gcloud()
