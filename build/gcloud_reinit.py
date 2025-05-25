import os
import shutil
import datetime
import platform
import tarfile

def get_gcloud_config_dir():
    """
    Determines the gcloud configuration directory based on the operating system.
    Primarily targets Linux/macOS.
    """
    system = platform.system()
    if system == "Linux" or system == "Darwin":  # Darwin is macOS
        return os.path.expanduser("~/.config/gcloud")
    # Add Windows support here if needed in the future
    # elif system == "Windows":
    #     appdata = os.getenv("APPDATA")
    #     if appdata:
    #         return os.path.join(appdata, "gcloud")
    print(f"Unsupported OS for automatic gcloud config directory detection: {system}")
    return None

def backup_gcloud_config(config_dir: str):
    """
    Creates a timestamped .tar.gz backup of the specified config_dir.
    Stores the backup in '~/gcloud_config_backups/'.
    """
    if not os.path.exists(config_dir):
        print(f"Configuration directory not found: {config_dir}")
        return None

    backup_base_dir = os.path.expanduser("~/gcloud_config_backups")
    if not os.path.exists(backup_base_dir):
        try:
            os.makedirs(backup_base_dir)
            print(f"Created backup directory: {backup_base_dir}")
        except OSError as e:
            print(f"Error creating backup directory {backup_base_dir}: {e}")
            return None
            
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_archive_name = f"gcloud_config_backup_{timestamp}.tar.gz"
    backup_archive_path = os.path.join(backup_base_dir, backup_archive_name)
    
    print(f"Backing up '{config_dir}' to '{backup_archive_path}'...")
    try:
        # Create a tar.gz file
        with tarfile.open(backup_archive_path, "w:gz") as tar:
            # Add the config_dir to the archive.
            # arcname ensures the path in the archive is just the directory name (e.g., 'gcloud')
            # instead of the full path.
            tar.add(config_dir, arcname=os.path.basename(config_dir))
        print(f"Successfully backed up to '{backup_archive_path}'")
        return backup_archive_path
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

def delete_gcloud_config(config_dir: str):
    """
    Deletes the specified gcloud configuration directory.
    """
    if not os.path.exists(config_dir):
        print(f"Configuration directory not found, nothing to delete: {config_dir}")
        return False # Or True, as the desired state (not existing) is met
    
    print(f"Deleting directory: {config_dir}")
    try:
        shutil.rmtree(config_dir)
        print(f"Successfully deleted '{config_dir}'")
        return True
    except Exception as e:
        print(f"Error deleting directory '{config_dir}': {e}")
        return False

def reset_gcloud_config():
    """
    Main function to reset gcloud configuration.
    Returns True if successful, False otherwise.
    """
    print("This script will reset your Google Cloud SDK (gcloud) configuration.")
    print("It can first create a backup of your current configuration (optional),")
    print("then delete the configuration directory.")
    print("This effectively undoes 'gcloud init' and removes all associated configurations,")
    print("accounts, and credentials stored by the gcloud CLI.")
    print("=" * 70)

    gcloud_config_path = get_gcloud_config_dir()

    if not gcloud_config_path:
        print("Could not determine the gcloud configuration directory for your operating system.")
        return False
        
    if not os.path.exists(gcloud_config_path):
        print(f"Google Cloud SDK configuration directory not found at '{gcloud_config_path}'.")
        print("It seems 'gcloud init' has not been run, or the configuration is not in the default location.")
        print("No action will be taken.")
        return True  # Consider this success since the desired state is achieved

    print(f"The gcloud configuration directory is: {gcloud_config_path}")
    print("-" * 70)

    delete_confirmation = input(f"Are you sure you want to DELETE the directory '{gcloud_config_path}'? (yes/no): ").strip().lower()
    if delete_confirmation != "yes":
        print("Operation cancelled by the user.")
        return False

    backup_file_path = None

    backup_choice_prompt = "Do you want to create a backup of this directory before deleting it? (yes/no): "
    backup_confirmation = input(backup_choice_prompt).strip().lower()

    if backup_confirmation == "yes":
        print("\\nStarting backup process...")
        backup_file_path = backup_gcloud_config(gcloud_config_path)
        if not backup_file_path:
            print("Backup failed. Aborting deletion to prevent data loss.")
            return False
        print("\\nBackup successful.")
    elif backup_confirmation == "no":
        print("\\nSkipping backup process as per user request.")
    else:
        print("Invalid input for backup choice. Assuming 'no' for safety. Skipping backup.")

    print("Proceeding with deletion...")
    delete_success = delete_gcloud_config(gcloud_config_path)

    if delete_success:
        print("\\nGoogle Cloud SDK configuration has been reset.")
        if backup_file_path:
            print(f"A backup of your old configuration was created at: {backup_file_path}")
        else:
            print("No backup was created as per your choice or due to an invalid backup option.")
        print("You will need to run 'gcloud init' again to reconfigure the CLI.")
        return True
    else:
        print("\\nDeletion failed. Your configuration directory may still be present.")
        if backup_file_path:
            print(f"A backup was created at: {backup_file_path}")
        return False


if __name__ == "__main__":
    # This allows the script to still be run standalone for testing
    reset_gcloud_config()
