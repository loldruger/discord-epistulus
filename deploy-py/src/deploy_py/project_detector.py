"""
프로젝트 정보 자동 감지 모듈
"""

import subprocess
import json
from typing import Any
from pathlib import Path


class ProjectDetector:
    """프로젝트 정보 자동 감지 클래스"""
    
    def __init__(self):
        self.project_root = Path.cwd()
    
    def validate_prerequisites(self) -> bool:
        """배포 전제조건 확인"""
        print("🔍 배포 전제조건을 확인하고 있습니다...")
        
        # Python 버전 체크
        if not self._check_python_version():
            return False
        
        # Git 저장소 확인
        if not (self.project_root / '.git').exists():
            print("❌ Git 저장소가 아닙니다.")
            return False
        
        # gcloud CLI 확인 및 설치
        if not self._check_and_setup_gcloud():
            return False
        
        # Docker 확인
        if not self._check_docker():
            return False
        
        # Dockerfile 확인
        if not (self.project_root / 'Dockerfile').exists():
            print("❌ Dockerfile이 프로젝트 루트에 없습니다.")
            return False
        
        # gcloud 인증 상태 확인
        if not self._check_gcloud_auth():
            return False
        
        print("✅ 모든 전제조건이 충족되었습니다.")
        return True
    
    def _check_python_version(self) -> bool:
        """Python 버전 확인"""
        import sys
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            print(f"❌ Python 3.8 이상이 필요합니다. 현재 버전: {python_version.major}.{python_version.minor}")
            return False
        print(f"✅ Python 버전: {python_version.major}.{python_version.minor}.{python_version.micro}")
        return True
    
    def _check_docker(self) -> bool:
        """Docker 설치 및 데몬 상태 확인"""
        try:
            # Docker CLI 확인
            subprocess.run(['docker', '--version'], 
                         check=True, capture_output=True)
            print("✅ Docker CLI 설치됨")
            
            # Docker 데몬 상태 확인
            subprocess.run(['docker', 'info'], 
                         check=True, capture_output=True)
            print("✅ Docker 데몬 실행 중")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Docker가 설치되지 않았거나 데몬이 실행되지 않았습니다.")
            print("   https://docs.docker.com/get-docker/ 에서 설치하세요.")
            return False
    
    def _check_and_setup_gcloud(self) -> bool:
        """gcloud CLI 확인 및 설정"""
        try:
            # gcloud CLI 확인
            subprocess.run(['gcloud', '--version'], check=True, capture_output=True, text=True)
            print("✅ gcloud CLI 설치됨")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ gcloud CLI가 설치되지 않았습니다.")
            print("   https://cloud.google.com/sdk/docs/install 에서 설치하세요.")
            return False
    
    def _check_gcloud_auth(self) -> bool:
        """gcloud 인증 상태 확인"""
        try:
            # 활성 계정 확인
            result = subprocess.run([
                'gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'
            ], capture_output=True, text=True, check=True)
            
            if result.stdout.strip():
                print(f"✅ gcloud 인증됨: {result.stdout.strip()}")
                return True
            else:
                print("❌ gcloud 인증이 필요합니다.")
                print("   'gcloud auth login' 명령어를 실행하세요.")
                return False
        except subprocess.CalledProcessError:
            print("❌ gcloud 인증 상태를 확인할 수 없습니다.")
            print("   'gcloud auth login' 명령어를 실행하세요.")
            return False
    
    def get_github_info(self) -> dict[str, str]:
        """GitHub 저장소 정보 감지"""
        try:
            # Git remote origin URL 가져오기
            result = subprocess.run([
                'git', 'remote', 'get-url', 'origin'
            ], capture_output=True, text=True, check=True)
            
            remote_url = result.stdout.strip()
            
            # GitHub URL 파싱
            if 'github.com' in remote_url:
                if remote_url.startswith('git@github.com:'):
                    # SSH 형식: git@github.com:owner/repo.git
                    repo_path = remote_url.replace('git@github.com:', '').replace('.git', '')
                elif remote_url.startswith('https://github.com/'):
                    # HTTPS 형식: https://github.com/owner/repo.git
                    repo_path = remote_url.replace('https://github.com/', '').replace('.git', '')
                else:
                    raise ValueError("알 수 없는 GitHub URL 형식")
                
                owner, repo = repo_path.split('/')
                return {'owner': owner, 'repo': repo}
            else:
                raise ValueError("GitHub 저장소가 아닙니다")
                
        except (subprocess.CalledProcessError, ValueError) as e:
            raise Exception(f"GitHub 정보를 가져올 수 없습니다: {e}")
    
    def get_gcp_info(self) -> dict[str, str]:
        """Google Cloud 프로젝트 정보 감지"""
        try:
            # 현재 활성화된 GCP 프로젝트 가져오기
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'project'
            ], capture_output=True, text=True, check=True)
            
            project_id = result.stdout.strip()
            if not project_id or project_id == '(unset)':
                raise ValueError("활성화된 GCP 프로젝트가 없습니다")
            
            # 프로젝트 번호 가져오기
            result = subprocess.run([
                'gcloud', 'projects', 'describe', project_id,
                '--format', 'value(projectNumber)'
            ], capture_output=True, text=True, check=True)
            
            project_number = result.stdout.strip()
            
            return {
                'project_id': project_id,
                'project_number': project_number
            }
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"GCP 정보를 가져올 수 없습니다: {e}")
    
    def get_project_info(self) -> dict[str, Any]:
        """전체 프로젝트 정보 수집"""
        try:
            github_info = self.get_github_info()
            gcp_info = self.get_gcp_info()
            
            return {
                'github': github_info,
                'gcp': gcp_info
            }
        except Exception as e:
            print(f"❌ 프로젝트 정보 감지 실패: {e}")
            raise


def main():
    """테스트용 메인 함수"""
    detector = ProjectDetector()
    
    if detector.validate_prerequisites():
        try:
            info = detector.get_project_info()
            print("✅ 프로젝트 정보:")
            print(json.dumps(info, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ 오류: {e}")
    else:
        print("❌ 전제조건이 충족되지 않았습니다.")


if __name__ == "__main__":
    main()
