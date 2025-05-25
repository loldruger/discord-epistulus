"""
gcloud CLI 초기화 및 재설정 관리 모듈
"""
import shutil
import datetime
import platform
import tarfile
import subprocess
from pathlib import Path


class GCloudManager:
    """gcloud CLI 설정 관리 클래스"""
    
    def __init__(self):
        self.config_dir = self._get_gcloud_config_dir()
        self.backup_dir = Path.home() / "gcloud_config_backups"
    
    def _get_gcloud_config_dir(self) -> Path | None:
        """운영체제에 따른 gcloud 설정 디렉토리 경로 반환"""
        system = platform.system()
        if system in ["Linux", "Darwin"]:  # Darwin = macOS
            return Path.home() / ".config" / "gcloud"
        else:
            print(f"❌ 지원되지 않는 OS: {system}")
            return None
    
    def is_gcloud_configured(self) -> bool:
        """gcloud가 설정되어 있는지 확인"""
        try:
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'account'
            ], capture_output=True, text=True, check=True)
            
            account = result.stdout.strip()
            if account and account != "(unset)":
                return True
            return False
        except subprocess.CalledProcessError:
            return False
    
    def get_current_config(self) -> dict[str, str]:
        """현재 gcloud 설정 정보 반환"""
        config: dict[str, str] = {}
        
        try:
            # 현재 계정
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'account'
            ], capture_output=True, text=True, check=True)
            config['account'] = result.stdout.strip()
            
            # 현재 프로젝트
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'project'
            ], capture_output=True, text=True, check=True)
            config['project'] = result.stdout.strip()
            
            # 현재 지역
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'compute/region'
            ], capture_output=True, text=True, check=True)
            config['region'] = result.stdout.strip()
            
        except subprocess.CalledProcessError:
            pass
        
        return config
    
    def backup_config(self) -> Path | None:
        """gcloud 설정 백업"""
        if not self.config_dir or not self.config_dir.exists():
            print("❌ gcloud 설정 디렉토리를 찾을 수 없습니다")
            return None
        
        # 백업 디렉토리 생성
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"❌ 백업 디렉토리 생성 실패: {e}")
            return None
        
        # 백업 파일명 생성
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"gcloud_config_backup_{timestamp}.tar.gz"
        
        print(f"🔄 gcloud 설정 백업 중... → {backup_file}")
        
        try:
            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(self.config_dir, arcname="gcloud")
            
            print(f"✅ 백업 완료: {backup_file}")
            return backup_file
            
        except Exception as e:
            print(f"❌ 백업 실패: {e}")
            return None
    
    def reset_config(self, create_backup: bool = True) -> bool:
        """gcloud 설정 완전 재설정"""
        if not self.config_dir or not self.config_dir.exists():
            print("✅ gcloud 설정이 이미 초기 상태입니다")
            return True
        
        print("🔄 gcloud 설정 재설정 시작...")
        
        backup_path = None
        if create_backup:
            backup_path = self.backup_config()
            if not backup_path:
                print("❌ 백업 실패로 인해 재설정을 중단합니다")
                return False
        
        # 설정 디렉토리 삭제
        try:
            shutil.rmtree(self.config_dir)
            print(f"✅ gcloud 설정 디렉토리 삭제 완료: {self.config_dir}")
            
            if backup_path:
                print(f"💾 백업 파일: {backup_path}")
            
            print("⚠️  gcloud init을 실행하여 재설정해주세요")
            return True
            
        except Exception as e:
            print(f"❌ 설정 삭제 실패: {e}")
            return False
    
    def init_interactive(self) -> bool:
        """대화형 gcloud 초기화"""
        print("🚀 gcloud 대화형 초기화 시작...")
        
        try:
            subprocess.run(['gcloud', 'init'], check=True)
            print("✅ gcloud 초기화 완료")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ gcloud 초기화 실패: {e}")
            return False
    
    def quick_setup(self, account: str, project_id: str, region: str = "asia-northeast3") -> bool:
        """빠른 gcloud 설정"""
        print(f"⚡ gcloud 빠른 설정: {account}, {project_id}, {region}")
        
        try:
            # 계정 설정
            subprocess.run([
                'gcloud', 'auth', 'login', account
            ], check=True)
            
            # 프로젝트 설정
            subprocess.run([
                'gcloud', 'config', 'set', 'project', project_id
            ], check=True)
            
            # 지역 설정
            subprocess.run([
                'gcloud', 'config', 'set', 'compute/region', region
            ], check=True)
            
            print("✅ gcloud 빠른 설정 완료")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ gcloud 설정 실패: {e}")
            return False
    
    def show_current_config(self) -> None:
        """현재 gcloud 설정 정보 출력"""
        print("\n📋 현재 gcloud 설정:")
        print("=" * 40)
        
        if not self.is_gcloud_configured():
            print("❌ gcloud가 설정되지 않았습니다")
            return
        
        config = self.get_current_config()
        
        for key, value in config.items():
            if value and value != "(unset)":
                print(f"  {key.capitalize()}: {value}")
            else:
                print(f"  {key.capitalize()}: (설정되지 않음)")
        
        print("=" * 40)
