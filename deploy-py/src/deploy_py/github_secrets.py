"""
GitHub Secrets 자동 설정 모듈
GitHub REST API를 사용하여 repository secrets를 설정합니다.
"""

import sys
import base64
import requests
from typing import Any

try:
    from nacl import public  # type: ignore[import-untyped]
    nacl_available = True
except ImportError:
    nacl_available = False
    print("PyNaCl 라이브러리가 설치되지 않았습니다. GitHub secrets 암호화를 위해 설치가 필요합니다:")
    print("pip install PyNaCl")


class GitHubSecretsManager:
    """GitHub repository secrets 관리 클래스"""
    
    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Secrets-Setup-Script"
        }
    
    def get_public_key(self) -> dict[str, Any]:
        """Repository의 public key 가져오기"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/secrets/public-key"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get public key: {response.status_code} - {response.text}")
    
    def encrypt_secret(self, public_key_data: dict[str, Any], secret_value: str) -> str:
        """Secret 값을 public key로 암호화 (NaCl sealed box 사용)"""
        if not nacl_available:
            raise ImportError("PyNaCl 라이브러리가 필요합니다. 'pip install PyNaCl'로 설치하세요.")
        
        try:
            # GitHub API 공개키는 base64로 인코딩된 NaCl 공개키
            public_key_bytes = base64.b64decode(public_key_data["key"])
            public_key_obj = public.PublicKey(public_key_bytes)  # type: ignore[attr-defined]
            
            # sealed box로 암호화
            sealed_box = public.SealedBox(public_key_obj)  # type: ignore[attr-defined]
            encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))  # type: ignore[attr-defined]
            
            return base64.b64encode(encrypted).decode('utf-8')  # type: ignore[arg-type]
            
        except Exception as e:
            print(f"암호화 중 오류: {e}")
            print(f"공개키 데이터: {public_key_data}")
            raise
    
    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """Secret 설정"""
        try:
            # Public key 가져오기
            public_key_data = self.get_public_key()
            
            # Secret 암호화
            encrypted_value = self.encrypt_secret(public_key_data, secret_value)
            
            # Secret 설정
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/secrets/{secret_name}"
            data = {
                "encrypted_value": encrypted_value,
                "key_id": public_key_data["key_id"]
            }
            
            response = requests.put(url, headers=self.headers, json=data)
            return response.status_code in [201, 204]
            
        except Exception as e:
            print(f"❌ Error setting secret {secret_name}: {e}")
            return False
    
    def list_secrets(self) -> list[dict[str, Any]]:
        """설정된 secrets 목록 가져오기"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/secrets"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json().get("secrets", [])
        else:
            return []
    
    def delete_secret(self, secret_name: str) -> bool:
        """Secret 삭제"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/secrets/{secret_name}"
        response = requests.delete(url, headers=self.headers)
        return response.status_code == 204


def setup_github_secrets(config: dict[str, Any]) -> bool:
    """GitHub secrets 설정"""
    print("🔧 GitHub Secrets 자동 설정")
    print("=" * 40)
    
    # GitHub token 확인
    github_token = config.get('github_token')
    if not github_token:
        print("❌ GitHub 토큰이 제공되지 않았습니다.")
        print("수동으로 GitHub Secrets를 설정해야 합니다.")
        return False
    
    # Repository 정보
    repo_owner = config['github']['owner']
    repo_name = config['github']['repo']
    
    print(f"✅ Repository: {repo_owner}/{repo_name}")
    print()
    
    # WIF Provider 경로 생성
    wif_provider = f"projects/{config['gcp']['project_number']}/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider"
    
    # Secrets 정의 (동적으로 생성)
    secrets = {
        "WIF_PROVIDER": wif_provider,
        "WIF_SERVICE_ACCOUNT": f"github-actions-sa@{config['gcp']['project_id']}.iam.gserviceaccount.com",
        "GCP_PROJECT_ID": config['gcp']['project_id'],
        "GAR_LOCATION": config['gar_location'],
        "GAR_REPOSITORY": config['gar_repository'],
        "SERVICE_NAME": config['service_name']
    }
    
    # Discord 봇 토큰이 있으면 추가
    if config.get('discord_token'):
        secrets['DISCORD_BOT_TOKEN'] = config['discord_token']
    
    print("📝 설정할 Secrets:")
    for key in secrets.keys():
        if key == 'DISCORD_BOT_TOKEN':
            print(f"  - {key} (Discord 봇 토큰)")
        else:
            print(f"  - {key}")
    print()
    
    # GitHub Secrets Manager 초기화
    try:
        manager = GitHubSecretsManager(github_token, repo_owner, repo_name)
    except Exception as e:
        print(f"❌ GitHub API 연결 실패: {e}")
        return False
    
    print("🚀 Secrets 설정 중...")
    
    # Secrets 설정
    success_count = 0
    total_count = len(secrets)
    
    for secret_name, secret_value in secrets.items():
        print(f"  설정 중: {secret_name} ... ", end="", flush=True)
        
        if manager.set_secret(secret_name, secret_value):
            print("✅")
            success_count += 1
        else:
            print("❌")
    
    print()
    
    if success_count == total_count:
        print(f"🎉 모든 secrets가 성공적으로 설정되었습니다! ({success_count}/{total_count})")
    else:
        print(f"⚠️  일부 secrets 설정에 실패했습니다. ({success_count}/{total_count})")
    
    print()
    if not config.get('discord_token'):
        print("💡 Discord 봇 토큰 설정:")
        print("  GitHub → Repository → Settings → Secrets and variables → Actions")
        print("  'DISCORD_BOT_TOKEN' secret을 수동으로 추가하세요.")
        print()
    
    print("✅ GitHub Actions 워크플로우가 이제 사용 가능합니다!")
    
    return success_count == total_count


if __name__ == "__main__":
    # 테스트용 설정
    test_config = {
        'github': {'owner': 'loldruger', 'repo': 'discord-epistulus'},
        'gcp': {'project_id': 'epistulus', 'project_number': '475438547541'},
        'gar_location': 'asia-northeast3',
        'gar_repository': 'discord-epistulus-repo',
        'service_name': 'discord-epistulus-service',
        'github_token': 'test_token'
    }
    
    try:
        setup_github_secrets(test_config)
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류: {e}")
        sys.exit(1)
