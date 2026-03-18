"""
System Settings API Routes

Provides endpoints for managing global system configuration (BYOK).
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import get_db, SystemSettings, User
from api.schemas import SystemSettingsRequest, SystemSettingsResponse, SuccessResponse
from api.deps import get_current_user


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _get_or_create_settings(db, user: User) -> SystemSettings:
    """Get existing settings for user or create default instance"""
    settings = db.query(SystemSettings).filter(SystemSettings.user_id == user.id).first()
    if not settings:
        settings = SystemSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_model=SystemSettingsResponse)
async def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SystemSettingsResponse:
    """
    Get current system settings.
    
    API keys are not returned directly - only a boolean indicating if they are set.
    Webhook URLs are returned in full.
    """
    settings = _get_or_create_settings(db, current_user)
    
    return SystemSettingsResponse(
        id=settings.id,

        groq_api_key_set=bool(settings.groq_api_key),
        openrouter_api_key_set=bool(settings.openrouter_api_key),
        github_token_set=bool(settings.github_token),
        slack_webhook_url=settings.slack_webhook_url,
        discord_webhook_url=settings.discord_webhook_url,
        azure_subscription_id=settings.azure_subscription_id,
        azure_tenant_id_set=bool(settings.azure_tenant_id),
        azure_client_id_set=bool(settings.azure_client_id),
        azure_client_secret_set=bool(settings.azure_client_secret),
        is_configured=bool(settings.is_configured),
        updated_at=settings.updated_at
    )


@router.post("", response_model=SuccessResponse)
async def update_settings(
    request: SystemSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Update system settings.
    
    Only provided fields are updated. Empty strings clear the field.
    API keys are encrypted before storage.
    """
    from services.credentials import get_credential_manager
    cred_manager = get_credential_manager()
    
    settings = _get_or_create_settings(db, current_user)
    
    # Use CredentialManager to store and encrypt credentials
    cred_manager.store_system_credentials(
        settings,

        groq_api_key=request.groq_api_key,
        openrouter_api_key=request.openrouter_api_key,
        github_token=request.github_token,
        slack_webhook_url=request.slack_webhook_url,
        discord_webhook_url=request.discord_webhook_url,
        azure_subscription_id=request.azure_subscription_id,
        azure_tenant_id=request.azure_tenant_id,
        azure_client_id=request.azure_client_id,
        azure_client_secret=request.azure_client_secret
    )
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    
    return SuccessResponse(
        message="Settings updated successfully",
        data={

            "groq_api_key_set": bool(settings.groq_api_key),
            "openrouter_api_key_set": bool(settings.openrouter_api_key),
            "github_token_set": bool(settings.github_token),
            "slack_webhook_url_set": bool(settings.slack_webhook_url),
            "discord_webhook_url_set": bool(settings.discord_webhook_url)
        }
    )


@router.delete("", response_model=SuccessResponse)
async def reset_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SuccessResponse:
    """
    Reset all system settings to defaults (clear all values).
    """
    settings = _get_or_create_settings(db, current_user)
    

    settings.groq_api_key = None
    settings.openrouter_api_key = None
    settings.github_token = None
    settings.slack_webhook_url = None
    settings.discord_webhook_url = None
    settings.azure_subscription_id = None
    settings.azure_tenant_id = None
    settings.azure_client_id = None
    settings.azure_client_secret = None
    settings.is_configured = 0
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    
    return SuccessResponse(message="Settings reset to defaults")
