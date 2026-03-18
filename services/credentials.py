import os
from typing import Dict, Optional
from cryptography.fernet import Fernet
import logging
from api.config import settings
from models.models import Project

logger = logging.getLogger(__name__)

class CredentialManager:
    def __init__(self):
        # Load environment variables from .env file if not already loaded
        from dotenv import load_dotenv
        import os
        load_dotenv()  # Load .env file

        encryption_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")

        if not encryption_key:
            logger.warning("No CREDENTIAL_ENCRYPTION_KEY found, using generated key (NOT FOR PRODUCTION)")
            encryption_key = Fernet.generate_key().decode()
        else:
            logger.info("CREDENTIAL_ENCRYPTION_KEY loaded successfully")

        try:
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception as e:
            logger.error(f"Cipher initialization failed: {e}")
            self.cipher = None
    
    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        
        if not self.cipher:
            return value
        
        try:
            return self.cipher.encrypt(value.encode()).decode()
        except Exception as e:
            return None
    
    def decrypt(self, encrypted_value: Optional[str]) -> Optional[str]:
        if not encrypted_value:
            return None
        
        if not self.cipher:
            return encrypted_value
        
        try:
            return self.cipher.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            return encrypted_value
    
    def get_credentials_for_project(self, project: Project) -> Dict[str, str]:
        credentials = {}

        if project.github_token and not project.use_system_credentials:
            credentials["github_token"] = self.decrypt(project.github_token)        
        else:
            credentials["github_token"] = settings.github_token        
        if project.slack_webhook_url and not project.use_system_credentials:
            credentials["slack_webhook"] = project.slack_webhook_url        
        else:
            credentials["slack_webhook"] = settings.slack_webhook_url        
        if project.discord_webhook_url and not project.use_system_credentials:
            credentials["discord_webhook"] = project.discord_webhook_url        
        else:
            credentials["discord_webhook"] = settings.discord_webhook_url     

        return credentials
    
    def store_credentials(
        self,
        project: Project,
        github_token: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        discord_webhook: Optional[str] = None
    ) -> None:
        """Store credentials for a project. Only github_token is encrypted."""
        if github_token:
            project.github_token = self.encrypt(github_token)
            project.use_system_credentials = 0        
        if slack_webhook:
            project.slack_webhook_url = slack_webhook
            project.use_system_credentials = 0        
        if discord_webhook:
            project.discord_webhook_url = discord_webhook
            project.use_system_credentials = 0        
        if not any([github_token, slack_webhook, discord_webhook]):
            project.use_system_credentials = 1    
    
    def store_system_credentials(
        self,
        system_settings,
        groq_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        github_token: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        azure_subscription_id: Optional[str] = None,
        azure_tenant_id: Optional[str] = None,
        azure_client_id: Optional[str] = None,
        azure_client_secret: Optional[str] = None
    ) -> None:
        if groq_api_key is not None:
            system_settings.groq_api_key = self.encrypt(groq_api_key) if groq_api_key else None
        
        if openrouter_api_key is not None:
            system_settings.openrouter_api_key = self.encrypt(openrouter_api_key) if openrouter_api_key else None
        
        if github_token is not None:
            system_settings.github_token = self.encrypt(github_token) if github_token else None

        if slack_webhook_url is not None:
            system_settings.slack_webhook_url = slack_webhook_url if slack_webhook_url else None
        
        if discord_webhook_url is not None:
            system_settings.discord_webhook_url = discord_webhook_url if discord_webhook_url else None
        
        if azure_subscription_id is not None:
            system_settings.azure_subscription_id = azure_subscription_id if azure_subscription_id else None
            
        if azure_tenant_id is not None:
            system_settings.azure_tenant_id = azure_tenant_id if azure_tenant_id else None

        if azure_client_id is not None:
            system_settings.azure_client_id = self.encrypt(azure_client_id) if azure_client_id else None

        if azure_client_secret is not None:
            system_settings.azure_client_secret = self.encrypt(azure_client_secret) if azure_client_secret else None
        
        system_settings.is_configured = 1
    
    def get_system_credentials(self, system_settings) -> Dict[str, Optional[str]]:
        return {
            "groq_api_key": self.decrypt(system_settings.groq_api_key) if system_settings.groq_api_key else None,
            "openrouter_api_key": self.decrypt(system_settings.openrouter_api_key) if system_settings.openrouter_api_key else None,
            "github_token": self.decrypt(system_settings.github_token) if system_settings.github_token else None,
            "slack_webhook_url": system_settings.slack_webhook_url,
            "discord_webhook_url": system_settings.discord_webhook_url,
            "azure_subscription_id": system_settings.azure_subscription_id,
            "azure_tenant_id": system_settings.azure_tenant_id,
            "azure_client_id": self.decrypt(system_settings.azure_client_id) if system_settings.azure_client_id else None,
            "azure_client_secret": self.decrypt(system_settings.azure_client_secret) if system_settings.azure_client_secret else None,
        }


credential_manager = CredentialManager()

def get_credential_manager() -> CredentialManager:
    return credential_manager
