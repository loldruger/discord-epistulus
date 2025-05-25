#!/usr/bin/env python3
"""
GitHub Secrets Setup Script
GitHub REST API를 사용하여 repository secrets을 자동으로 설정합니다.
"""
import requests
import json
import base64
import os
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes


class GitHubSecretsManager:
    """GitHub repository secrets 관리 클래스"""
    
    def __init__(self, github_token: str, repo_owner: str, repo_name: str):
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    
    def get_public_key(self):
        """Repository의 public key 가져오기 (secrets 암호화용)"""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/secrets/public-key"
        
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to get public key: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    
    def encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Secret 값을 public key로 암호화"""
        # Base64 디코딩
        public_key_bytes = base64.b64decode(public_key)
        
        # Public key 로드
        public_key_obj = serialization.load_der_public_key(public_key_bytes)
        
        # 암호화
        encrypted = public_key_obj.encrypt(
            secret_value.encode('utf-8'),
            padding.PKCS1v15()
        )
        
        # Base64 인코딩하여 반환
        return base64.b64encode(encrypted).decode('utf-8')
    
    def create_or_update_secret(self, secret_name: str, secret_value: str) -> bool:
        """Secret 생성 또는 업데이트"""
        # Public key 가져오기
        public_key_data = self.get_public_key()
        if not public_key_data:
            return False
        
        public_key = public_key_data['key']
        key_id = public_key_data['key_id']
        
        # Secret 암호화
        try:
            encrypted_value = self.encrypt_secret(public_key, secret_value)
        except Exception as e:
            print(f"❌ Failed to encrypt secret {secret_name}: {e}")
            return False
        
        # Secret 업데이트 API 호출
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/secrets/{secret_name}"
        data = {
            "encrypted_value": encrypted_value,
            "key_id": key_id
        }
        
        response = requests.put(url, headers=self.headers, json=data)
        
        if response.status_code in [201, 204]:
            print(f"✅ Secret '{secret_name}' 설정 완료")
            return True
        else:
            print(f"❌ Failed to set secret '{secret_name}': {response.status_code}")
            print(f"Response: {response.text}")
            return False
    
    def setup_all_secrets(self, secrets_dict: dict) -> bool:
        """모든 secrets 설정"""
        print(f"🚀 Setting up GitHub secrets for {self.repo_owner}/{self.repo_name}")
        
        success_count = 0
        total_count = len(secrets_dict)
        
        for secret_name, secret_value in secrets_dict.items():
            if self.create_or_update_secret(secret_name, secret_value):
                success_count += 1
            else:
                print(f"⚠️ Failed to set secret: {secret_name}")
        
        print(f"\n📊 Results: {success_count}/{total_count} secrets configured successfully")
        
        if success_count == total_count:
            print("🎉 All secrets configured successfully!")
            return True
        else:
            print("⚠️ Some secrets failed to configure")
            return False


def main():
    """메인 함수"""
    # GitHub Personal Access Token 확인
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("❌ GITHUB_TOKEN 환경변수가 설정되지 않았습니다.")
        print("GitHub Personal Access Token을 생성하고 설정해주세요:")
        print("1. https://github.com/settings/tokens 방문")
        print("2. 'Generate new token (classic)' 클릭")
        print("3. 'repo' 권한 선택")
        print("4. 토큰 생성 후 환경변수로 설정: export GITHUB_TOKEN=your_token")
        return False
    
    # Repository 정보
    repo_owner = "loldruger"  # GitHub 사용자명
    repo_name = "discord-epistulus"  # Repository 이름
    
    # 설정할 secrets
    secrets = {
        "WIF_PROVIDER": "projects/475438547541/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider",
        "WIF_SERVICE_ACCOUNT": "github-actions-sa@epistulus.iam.gserviceaccount.com",
        "GCP_PROJECT_ID": "epistulus",
        "GAR_LOCATION": "asia-northeast3",
        "GAR_REPOSITORY": "discord-epistulus-repo",
        "SERVICE_NAME": "discord-epistulus-service"
    }
    
    # GitHub Secrets Manager 초기화
    manager = GitHubSecretsManager(github_token, repo_owner, repo_name)
    
    # Secrets 설정
    success = manager.setup_all_secrets(secrets)
    
    if success:
        print("\n🎯 다음 단계:")
        print("1. Discord 봇 토큰이 있다면 수동으로 추가:")
        print("   DISCORD_BOT_TOKEN: your_discord_bot_token")
        print("2. GitHub에 코드를 푸시하면 자동 배포가 시작됩니다!")
        return True
    else:
        print("\n❌ 일부 secrets 설정에 실패했습니다. 수동으로 설정해주세요.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
