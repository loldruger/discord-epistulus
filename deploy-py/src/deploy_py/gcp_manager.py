"""
Google Cloud 리소스 배포 및 관리 모듈
"""

import subprocess
from typing import Any
from pathlib import Path

from .config_manager import ConfigManager


class GCPDeploymentManager:
    """Google Cloud Platform 배포 관리 클래스"""
    
    def __init__(self, config: dict[str, Any], project_root: Path | None = None):
        self.config = config
        self.project_id = config['gcp']['project_id']
        self.project_number = config['gcp']['project_number']
        self.project_root = project_root or Path.cwd()
        self.config_manager = ConfigManager(self.project_root) if project_root else None
    
    def initialize_environment(self) -> bool:
        """환경 전체 초기화 수행"""
        print("🚀 배포 환경 초기화 시작...")
        
        try:
            # 1. 설정 파일 로드 및 검증
            if not self._verify_project_config():
                return False
            
            # 2. 환경 변수 설정
            if self.config_manager:
                self.config_manager.setup_environment_variables()
            
            # 3. 기본 설정 적용
            if not self._apply_default_settings():
                return False
            
            # 4. API 활성화
            if not self.enable_required_apis():
                return False
            
            # 5. Artifact Registry 설정
            if not self.setup_artifact_registry():
                return False
            
            print("✅ 환경 초기화 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 환경 초기화 실패: {e}")
            return False
    
    def _verify_project_config(self) -> bool:
        """프로젝트 설정 검증 및 초기화"""
        print("📋 프로젝트 설정 검증 중...")
        
        # 설정 파일 검증
        if self.config_manager:
            if not self.config_manager.validate_config():
                print("❌ 설정 파일 검증 실패")
                return False
        
        # GCP 프로젝트 ID 검증
        if not self.project_id:
            print("❌ GCP 프로젝트 ID가 설정되지 않았습니다")
            return False
        
        try:
            # 현재 프로젝트 설정 확인
            result = subprocess.run([
                'gcloud', 'config', 'get-value', 'project'
            ], capture_output=True, text=True, check=True)
            
            current_project = result.stdout.strip()
            if current_project != self.project_id:
                print(f"⚠️  프로젝트 설정을 변경합니다: {current_project} → {self.project_id}")
                subprocess.run([
                    'gcloud', 'config', 'set', 'project', self.project_id
                ], check=True)
            
            print(f"✅ 프로젝트 설정 완료: {self.project_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 프로젝트 설정 검증 실패: {e}")
            return False
    
    def _apply_default_settings(self) -> bool:
        """기본 설정 적용 및 환경 설정"""
        print("⚙️ 기본 설정 적용 중...")
        
        try:
            # 설정 파일에서 기본값 적용
            if self.config_manager:
                gcp_config = self.config_manager.get_gcp_config()
                
                # 기본 region 설정
                if not gcp_config.get('region'):
                    self.config_manager.update_config('gcp', 'region', 'asia-northeast3')
                
                # 기본 artifact registry 설정
                if not gcp_config.get('artifact_registry'):
                    self.config_manager.update_config('gcp', 'artifact_registry', {
                        'location': 'asia-northeast3',
                        'repository': 'discord-epistulus-repo'
                    })
                
                # 업데이트된 설정 다시 로드
                gcp_config = self.config_manager.get_gcp_config()
            
            # gcloud 기본 설정 적용
            if self.config_manager:
                gcp_config = self.config_manager.get_gcp_config()
                default_region = gcp_config.get('region', 'asia-northeast3')
                default_location = gcp_config.get('artifact_registry', {}).get('location', 'asia-northeast3')
            else:
                default_region = self.config.get('service_region', 'asia-northeast3')
                default_location = self.config.get('gar_location', 'asia-northeast3')
            
            subprocess.run([
                'gcloud', 'config', 'set', 'run/region', default_region
            ], check=True, capture_output=True)
            
            subprocess.run([
                'gcloud', 'config', 'set', 'artifacts/location', default_location
            ], check=True, capture_output=True)
            
            print(f"✅ 기본 지역 설정: {default_region}")
            print(f"✅ 기본 저장소 위치: {default_location}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 기본 설정 적용 실패: {e}")
            return False
    
    def enable_required_apis(self) -> bool:
        """필요한 API들 활성화"""
        print("🔧 필요한 Google Cloud API들을 활성화하는 중...")
        
        apis = [
            "run.googleapis.com",
            "artifactregistry.googleapis.com",
            "cloudbuild.googleapis.com",
            "iam.googleapis.com",
            "iamcredentials.googleapis.com",
            "sts.googleapis.com"
        ]
        
        try:
            for api in apis:
                print(f"  - {api} 활성화 중...")
                subprocess.run([
                    "gcloud", "services", "enable", api,
                    "--project", self.project_id
                ], check=True, capture_output=True)
            
            print("✅ 모든 필요한 API가 활성화되었습니다.")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ API 활성화 실패: {e}")
            return False
    
    def setup_artifact_registry(self) -> bool:
        """Artifact Registry 전체 설정"""
        print("📦 Artifact Registry 설정 중...")
        
        # Artifact Registry 저장소 생성
        if not self.create_artifact_registry():
            return False
        
        # Docker 인증 설정
        if not self.configure_docker_auth():
            return False
        
        print("✅ Artifact Registry 설정 완료")
        return True

    def create_artifact_registry(self) -> bool:
        """Artifact Registry 저장소 생성"""
        print("📦 Artifact Registry 저장소 생성 중...")
        
        location = self.config['gar_location']
        repository = self.config['gar_repository']
        
        try:
            # 저장소가 이미 존재하는지 확인
            try:
                subprocess.run([
                    "gcloud", "artifacts", "repositories", "describe", repository,
                    "--location", location,
                    "--project", self.project_id
                ], check=True, capture_output=True)
                print(f"✅ Artifact Registry 저장소 '{repository}'가 이미 존재합니다.")
                return True
            except subprocess.CalledProcessError:
                # 저장소가 존재하지 않으면 생성
                pass
            
            # 저장소 생성
            subprocess.run([
                "gcloud", "artifacts", "repositories", "create", repository,
                "--repository-format", "docker",
                "--location", location,
                "--description", "Discord Epistulus Docker images",
                "--project", self.project_id
            ], check=True)
            
            print(f"✅ Artifact Registry 저장소 '{repository}'가 생성되었습니다.")
            return True
            
        except Exception as e:
            print(f"❌ Artifact Registry 저장소 생성 실패: {e}")
            return False
    
    def configure_docker_auth(self) -> bool:
        """Docker 인증 설정"""
        print("🔑 Docker 인증 설정 중...")
        
        location = self.config['gar_location']
        
        try:
            subprocess.run([
                "gcloud", "auth", "configure-docker", f"{location}-docker.pkg.dev",
                "--quiet"
            ], check=True)
            
            print("✅ Docker 인증 설정 완료")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Docker 인증 설정 실패: {e}")
            return False
    
    def create_service_account(self) -> bool:
        """GitHub Actions용 서비스 계정 생성"""
        print("👤 서비스 계정 생성 중...")
        
        service_account_id = "github-actions-sa"
        
        try:
            # 서비스 계정이 이미 존재하는지 확인
            sa_email = f"{service_account_id}@{self.project_id}.iam.gserviceaccount.com"
            
            try:
                subprocess.run([
                    "gcloud", "iam", "service-accounts", "describe", sa_email,
                    "--project", self.project_id
                ], check=True, capture_output=True)
                print(f"✅ 서비스 계정 '{sa_email}'이 이미 존재합니다.")
                return True
            except subprocess.CalledProcessError:
                # 서비스 계정이 존재하지 않으면 생성
                pass
            
            # 서비스 계정 생성
            subprocess.run([
                "gcloud", "iam", "service-accounts", "create", service_account_id,
                "--display-name", "GitHub Actions Service Account",
                "--description", "Service account for GitHub Actions deployment",
                "--project", self.project_id
            ], check=True)
            
            # 필요한 역할 부여
            roles = [
                "roles/run.admin",
                "roles/artifactregistry.admin",
                "roles/storage.admin",
                "roles/iam.serviceAccountUser"
            ]
            
            for role in roles:
                subprocess.run([
                    "gcloud", "projects", "add-iam-policy-binding", self.project_id,
                    "--member", f"serviceAccount:{sa_email}",
                    "--role", role
                ], check=True)
            
            print(f"✅ 서비스 계정 '{sa_email}'이 생성되고 권한이 부여되었습니다.")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 서비스 계정 생성 실패: {e}")
            return False
    
    def setup_workload_identity_federation(self) -> str | None:
        """Workload Identity Federation 설정"""
        print("🔐 Workload Identity Federation 설정 중...")
        
        pool_id = "github-actions-pool"
        provider_id = "github-actions-provider"
        github_repo = f"{self.config['github']['owner']}/{self.config['github']['repo']}"
        
        try:
            # Workload Identity Pool 생성
            pool_name = f"projects/{self.project_number}/locations/global/workloadIdentityPools/{pool_id}"
            
            try:
                subprocess.run([
                    "gcloud", "iam", "workload-identity-pools", "describe", pool_id,
                    "--location", "global",
                    "--project", self.project_id
                ], check=True, capture_output=True)
                print(f"✅ Workload Identity Pool '{pool_id}'이 이미 존재합니다.")
            except subprocess.CalledProcessError:
                # Pool 생성
                subprocess.run([
                    "gcloud", "iam", "workload-identity-pools", "create", pool_id,
                    "--location", "global",
                    "--display-name", "GitHub Actions Pool",
                    "--description", "Workload Identity Pool for GitHub Actions",
                    "--project", self.project_id
                ], check=True)
                print(f"✅ Workload Identity Pool '{pool_id}'이 생성되었습니다.")
            
            # Provider 생성
            try:
                subprocess.run([
                    "gcloud", "iam", "workload-identity-pools", "providers", "describe", provider_id,
                    "--workload-identity-pool", pool_id,
                    "--location", "global",
                    "--project", self.project_id
                ], check=True, capture_output=True)
                print(f"✅ Workload Identity Provider '{provider_id}'이 이미 존재합니다.")
            except subprocess.CalledProcessError:
                # Provider 생성
                subprocess.run([
                    "gcloud", "iam", "workload-identity-pools", "providers", "create-oidc", provider_id,
                    "--workload-identity-pool", pool_id,
                    "--location", "global",
                    "--issuer-uri", "https://token.actions.githubusercontent.com",
                    "--attribute-mapping", "google.subject=assertion.sub,attribute.repository=assertion.repository",
                    "--attribute-condition", f"assertion.repository == '{github_repo}'",
                    "--project", self.project_id
                ], check=True)
                print(f"✅ Workload Identity Provider '{provider_id}'이 생성되었습니다.")
            
            # 서비스 계정에 바인딩
            sa_email = f"github-actions-sa@{self.project_id}.iam.gserviceaccount.com"
            member = f"principalSet://iam.googleapis.com/{pool_name}/attribute.repository/{github_repo}"
            
            subprocess.run([
                "gcloud", "iam", "service-accounts", "add-iam-policy-binding", sa_email,
                "--role", "roles/iam.workloadIdentityUser",
                "--member", member,
                "--project", self.project_id
            ], check=True)
            
            provider_path = f"{pool_name}/providers/{provider_id}"
            print(f"✅ Workload Identity Federation이 설정되었습니다.")
            return provider_path
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Workload Identity Federation 설정 실패: {e}")
            return None
    
    def build_and_push_image(self) -> bool:
        """Docker 이미지 빌드 및 푸시"""
        print("🐳 Docker 이미지 빌드 및 푸시 중...")
        
        location = self.config['gar_location']
        repository = self.config['gar_repository']
        image_name = "discord-epistulus"
        tag = "latest"
        
        image_uri = f"{location}-docker.pkg.dev/{self.project_id}/{repository}/{image_name}:{tag}"
        
        try:
            # Docker 인증 설정
            subprocess.run([
                "gcloud", "auth", "configure-docker", f"{location}-docker.pkg.dev",
                "--quiet"
            ], check=True)
            
            # 이미지 빌드
            subprocess.run([
                "docker", "build", "-t", image_uri, "."
            ], check=True, cwd=self.config.get('project_root', '.'))
            
            # 이미지 푸시
            subprocess.run([
                "docker", "push", image_uri
            ], check=True)
            
            print(f"✅ Docker 이미지가 빌드되고 푸시되었습니다: {image_uri}")
            self.config['image_uri'] = image_uri
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Docker 이미지 빌드/푸시 실패: {e}")
            return False
    
    def deploy_cloud_run_service(self) -> bool:
        """Cloud Run 서비스 배포"""
        print("☁️  Cloud Run 서비스 배포 중...")
        
        service_name = self.config['service_name']
        region = self.config['service_region']
        image_uri = self.config.get('image_uri')
        
        if not image_uri:
            print("❌ Docker 이미지 URI가 없습니다.")
            return False
        
        try:
            # 환경변수 설정
            env_vars: list[str] = []
            if self.config.get('discord_token'):
                env_vars.extend(["--set-env-vars", f"DISCORD_BOT_TOKEN={self.config['discord_token']}"])
            
            # Cloud Run 서비스 배포
            cmd = [
                "gcloud", "run", "deploy", service_name,
                "--image", image_uri,
                "--region", region,
                "--platform", "managed",
                "--allow-unauthenticated",
                "--port", "8080",
                "--project", self.project_id
            ]
            
            if env_vars:
                cmd.extend(env_vars)
            
            subprocess.run(cmd, check=True)
            
            # 서비스 URL 가져오기
            result = subprocess.run([
                "gcloud", "run", "services", "describe", service_name,
                "--region", region,
                "--format", "value(status.url)",
                "--project", self.project_id
            ], capture_output=True, text=True, check=True)
            
            service_url = result.stdout.strip()
            print(f"✅ Cloud Run 서비스가 배포되었습니다: {service_url}")
            self.config['service_url'] = service_url
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Cloud Run 서비스 배포 실패: {e}")
            return False
    
    def deploy_all(self) -> bool:
        """전체 배포 프로세스 실행"""
        print("🚀 전체 배포 프로세스를 시작합니다...")
        print()
        
        steps = [
            ("API 활성화", self.enable_required_apis),
            ("Artifact Registry 생성", self.create_artifact_registry),
            ("서비스 계정 생성", self.create_service_account),
            ("Workload Identity Federation 설정", lambda: self.setup_workload_identity_federation() is not None),
            ("Docker 이미지 빌드/푸시", self.build_and_push_image),
            ("Cloud Run 서비스 배포", self.deploy_cloud_run_service)
        ]
        
        for step_name, step_func in steps:
            print(f"📋 {step_name}...")
            if not step_func():
                print(f"❌ {step_name} 실패")
                return False
            print()
        
        print("🎉 모든 배포 단계가 성공적으로 완료되었습니다!")
        return True


def main():
    """테스트용 메인 함수"""
    # 테스트 설정
    test_config = {
        'gcp': {
            'project_id': 'epistulus',
            'project_number': '475438547541'
        },
        'github': {
            'owner': 'loldruger',
            'repo': 'discord-epistulus'
        },
        'gar_location': 'asia-northeast3',
        'gar_repository': 'discord-epistulus-repo',
        'service_name': 'discord-epistulus-service',
        'service_region': 'asia-northeast3'
    }
    
    manager = GCPDeploymentManager(test_config)
    success = manager.deploy_all()
    
    if success:
        print("✅ 배포 완료!")
    else:
        print("❌ 배포 실패!")


if __name__ == "__main__":
    main()
