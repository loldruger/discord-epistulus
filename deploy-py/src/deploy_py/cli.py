#!/usr/bin/env python3
"""
Discord Epistulus 자동 배포 CLI
"""

import sys
from pathlib import Path

from .interactive_setup import InteractiveSetup
from .gcp_manager import GCPDeploymentManager
from .github_secrets import setup_github_secrets
from .config_manager import ConfigManager
from .gcloud_manager import GCloudManager


class DeploymentCLI:
    """배포 CLI 클래스"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.config_manager = ConfigManager(self.project_root)


def show_gcloud_menu() -> str:
    """gcloud 초기화 메뉴 표시"""
    print("\n🔧 gcloud 설정 옵션:")
    print("1️⃣  현재 gcloud 설정 확인")
    print("2️⃣  gcloud 재초기화 (백업 포함)")
    print("3️⃣  gcloud 재초기화 (백업 없음)")
    print("4️⃣  gcloud 대화형 초기화")
    print("5️⃣  건너뛰기")
    
    while True:
        choice = input("\n선택하세요 (1-5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
            return choice
        print("❌ 올바른 옵션을 선택해주세요 (1-5)")


def handle_gcloud_initialization() -> bool:
    """gcloud 초기화 처리"""
    gcloud_mgr = GCloudManager()
    
    # 현재 gcloud 상태 확인
    if gcloud_mgr.is_gcloud_configured():
        gcloud_mgr.show_current_config()
        
        reinit = input("\n🔄 gcloud를 재초기화하시겠습니까? (y/n): ").strip().lower()
        if reinit != 'y':
            print("✅ 기존 gcloud 설정을 사용합니다")
            return True
        
        choice = show_gcloud_menu()
    else:
        print("\n❌ gcloud가 설정되지 않았습니다")
        print("🔧 gcloud 초기화가 필요합니다")
        choice = '4'  # 대화형 초기화로 바로 진행
    
    # 선택된 옵션 처리
    if choice == '1':
        gcloud_mgr.show_current_config()
        return True
    elif choice == '2':
        return gcloud_mgr.reset_config(create_backup=True) and gcloud_mgr.init_interactive()
    elif choice == '3':
        return gcloud_mgr.reset_config(create_backup=False) and gcloud_mgr.init_interactive()
    elif choice == '4':
        return gcloud_mgr.init_interactive()
    elif choice == '5':
        print("⏩ gcloud 초기화를 건너뜁니다")
        return True
    
    return False


def main() -> int:
    """메인 실행 함수"""
    print("🚀 Discord Epistulus 자동 배포 도구")
    print("=" * 50)
    
    try:
        # CLI 인스턴스 생성
        cli = DeploymentCLI()
        
        # gcloud 초기화 확인
        print("\n" + "="*50)
        print("🔧 gcloud 설정 확인")
        print("="*50)
        
        if not handle_gcloud_initialization():
            print("❌ gcloud 초기화에 실패했습니다.")
            return 1
        
        # 대화형 설정
        setup = InteractiveSetup()
        config = setup.run_interactive_setup()
        
        if not config:
            print("❌ 설정이 완료되지 않았습니다.")
            return 1
        
        # 프로젝트 루트 설정
        config['project_root'] = cli.project_root
        
        # GCP 배포
        print("\n" + "="*50)
        print("🏗️  Google Cloud 인프라 배포 시작")
        print("="*50)
        
        gcp_manager = GCPDeploymentManager(config, cli.project_root)
        if not gcp_manager.deploy_all():
            print("❌ GCP 배포에 실패했습니다.")
            return 1
        
        # GitHub Secrets 설정
        if config.get('github_token'):
            print("\n" + "="*50)
            print("🔑 GitHub Secrets 설정 시작")
            print("="*50)
            
            if not setup_github_secrets(config):
                print("⚠️  GitHub Secrets 설정에 일부 실패했지만 배포는 완료되었습니다.")
        
        # 최종 결과 출력
        print("\n" + "="*50)
        print("🎉 배포 완료!")
        print("="*50)
        
        if config.get('service_url'):
            print(f"🌐 서비스 URL: {config['service_url']}")
        
        print(f"🐳 Docker 이미지: {config.get('image_uri', 'N/A')}")
        print(f"☁️  Cloud Run 서비스: {config['service_name']}")
        print(f"📦 Artifact Registry: {config['gar_location']}/{config['gar_repository']}")
        
        if not config.get('discord_token'):
            print("\n💡 Discord 봇을 활성화하려면:")
            print("  1. GitHub → Repository → Settings → Secrets")
            print("  2. 'DISCORD_BOT_TOKEN' secret을 추가하세요")
        
        print("\n🔄 자동 배포가 설정되었습니다!")
        print("  GitHub에 코드를 푸시하면 자동으로 배포됩니다.")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다.")
        return 1
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류가 발생했습니다: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
