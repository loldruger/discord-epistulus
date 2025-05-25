"""
사용자 입력 및 대화형 설정 모듈
"""

import getpass
from typing import Any
from .project_detector import ProjectDetector  # type: ignore[import]


class InteractiveSetup:
    """대화형 설정 클래스"""
    
    def __init__(self):
        self.detector = ProjectDetector()  # type: ignore[misc]
        self.config: dict[str, Any] = {}
    
    def welcome(self):
        """환영 메시지 출력"""
        print("🚀 Discord Epistulus 자동 배포 도구")
        print("=" * 50)
        print("이 도구는 다음 작업을 자동화합니다:")
        print("  1. Google Cloud 인프라 설정")
        print("  2. Docker 이미지 빌드 및 배포")
        print("  3. Workload Identity Federation 설정")
        print("  4. GitHub Actions Secrets 설정")
        print("  5. Cloud Run 서비스 배포")
        print()
    
    def detect_and_confirm_project_info(self) -> bool:
        """프로젝트 정보 감지 및 확인"""
        print("🔍 프로젝트 정보를 자동으로 감지하고 있습니다...")
        
        # 전제조건 확인
        if not self.detector.validate_prerequisites():  # type: ignore[misc]
            return False
        
        # 프로젝트 정보 감지
        info = self.detector.get_project_info()  # type: ignore[misc]
        
        print()
        print("📋 감지된 프로젝트 정보:")
        print(f"  GitHub 저장소: {info['github']['owner']}/{info['github']['repo']}")  # type: ignore[index]
        print(f"  GCP 프로젝트: {info['gcp']['project_id']} (#{info['gcp']['project_number']})")  # type: ignore[index]
        print()
        
        # 사용자 확인
        confirm = input("위 정보가 정확합니까? (y/N): ").lower()
        if confirm != 'y':
            print("❌ 프로젝트 정보를 확인하고 다시 시도해주세요.")
            return False
        
        # 설정에 저장
        self.config.update(info)  # type: ignore[arg-type]
        return True
    
    def get_discord_bot_token(self) -> str | None:
        """Discord 봇 토큰 입력받기"""
        print()
        print("🤖 Discord 봇 설정")
        print("Discord 봇 토큰을 입력하세요 (선택사항 - 나중에 GitHub Secrets에서 설정 가능):")
        
        while True:
            choice = input("지금 토큰을 입력하시겠습니까? (y/N): ").lower()
            
            if choice == 'y':
                token = getpass.getpass("Discord 봇 토큰을 입력하세요 (입력이 숨겨집니다): ")
                if token.strip():
                    return token.strip()
                else:
                    print("❌ 토큰이 입력되지 않았습니다.")
                    continue
            else:
                print("ℹ️  Discord 봇 토큰은 나중에 GitHub Secrets에서 'DISCORD_BOT_TOKEN'으로 설정할 수 있습니다.")
                return None
    
    def get_github_token(self) -> str | None:
        """GitHub Personal Access Token 입력받기"""
        print()
        print("🔑 GitHub Personal Access Token")
        print("GitHub Secrets를 자동으로 설정하려면 Personal Access Token이 필요합니다.")
        print()
        print("토큰 생성 방법:")
        print("  1. GitHub → Settings → Developer settings → Personal access tokens")
        print("  2. 'Tokens (classic)' 선택")
        print("  3. 'Generate new token' → 'Generate new token (classic)'")
        print("  4. 다음 권한 선택: 'repo', 'workflow'")
        print("  5. 생성된 토큰 복사")
        print()
        
        while True:
            choice = input("GitHub Token을 입력하시겠습니까? (y/N): ").lower()
            
            if choice == 'y':
                token = getpass.getpass("GitHub Personal Access Token을 입력하세요: ")
                if token.strip() and token.startswith(('ghp_', 'github_pat_')):
                    return token.strip()
                else:
                    print("❌ 올바른 GitHub 토큰을 입력해주세요 (ghp_ 또는 github_pat_로 시작)")
                    continue
            else:
                print("ℹ️  GitHub Secrets는 나중에 수동으로 설정할 수 있습니다.")
                return None
    
    def get_deployment_config(self) -> dict[str, Any]:
        """배포 설정 입력받기"""
        print()
        print("⚙️  배포 설정")
        
        # 기본값들
        config = {
            "gar_location": "asia-northeast3",
            "gar_repository": "discord-epistulus-repo",
            "service_name": "discord-epistulus-service",
            "service_region": "asia-northeast3"
        }
        
        print(f"Artifact Registry 위치 (기본값: {config['gar_location']}): ", end="")
        location = input() or config['gar_location']
        config['gar_location'] = location
        
        print(f"Artifact Registry 저장소 이름 (기본값: {config['gar_repository']}): ", end="")
        repository = input() or config['gar_repository']
        config['gar_repository'] = repository
        
        print(f"Cloud Run 서비스 이름 (기본값: {config['service_name']}): ", end="")
        service_name = input() or config['service_name']
        config['service_name'] = service_name
        
        print(f"Cloud Run 서비스 지역 (기본값: {config['service_region']}): ", end="")
        service_region = input() or config['service_region']
        config['service_region'] = service_region
        
        return config
    
    def confirm_deployment(self) -> bool:
        """최종 배포 확인"""
        print()
        print("🚀 배포 계획")
        print("=" * 30)
        print(f"GitHub 저장소: {self.config['github']['owner']}/{self.config['github']['repo']}")
        print(f"GCP 프로젝트: {self.config['gcp']['project_id']}")
        print(f"Artifact Registry: {self.config['gar_location']}/{self.config['gar_repository']}")
        print(f"Cloud Run 서비스: {self.config['service_name']} ({self.config['service_region']})")
        
        if self.config.get('discord_token'):
            print("Discord 봇 토큰: ✅ 설정됨")
        else:
            print("Discord 봇 토큰: ⚠️  나중에 설정")
            
        if self.config.get('github_token'):
            print("GitHub 토큰: ✅ 설정됨")
        else:
            print("GitHub 토큰: ⚠️  나중에 설정")
        
        print()
        print("다음 작업들이 수행됩니다:")
        print("  1. Artifact Registry 저장소 생성")
        print("  2. IAM 서비스 계정 생성")
        print("  3. Workload Identity Federation 설정")
        print("  4. Docker 이미지 빌드 및 푸시")
        print("  5. Cloud Run 서비스 배포")
        if self.config.get('github_token'):
            print("  6. GitHub Secrets 자동 설정")
        print()
        
        confirm = input("위 작업을 진행하시겠습니까? (y/N): ").lower()
        return confirm == 'y'
    
    def run_interactive_setup(self) -> dict[str, Any]:
        """대화형 설정 실행"""
        self.welcome()
        
        # 프로젝트 정보 감지 및 확인
        if not self.detect_and_confirm_project_info():
            return {}
        
        # Discord 봇 토큰
        discord_token = self.get_discord_bot_token()
        if discord_token:
            self.config['discord_token'] = discord_token
        
        # GitHub 토큰
        github_token = self.get_github_token()
        if github_token:
            self.config['github_token'] = github_token
        
        # 배포 설정
        deploy_config = self.get_deployment_config()
        self.config.update(deploy_config)
        
        # 최종 확인
        if not self.confirm_deployment():
            print("❌ 배포가 취소되었습니다.")
            return {}
        
        return self.config


def main():
    """테스트용 메인 함수"""
    setup = InteractiveSetup()
    config = setup.run_interactive_setup()
    
    if config:
        print("✅ 설정이 완료되었습니다!")
        print(f"설정: {config}")
    else:
        print("❌ 설정이 완료되지 않았습니다.")


if __name__ == "__main__":
    main()
