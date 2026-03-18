import asyncio
import logging
from typing import Optional, Dict, Any
from enum import Enum
import apprise

from api.config import settings

logger = logging.getLogger(__name__)


class NotificationLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationService:
    LEVEL_MAP = {
        NotificationLevel.INFO: apprise.NotifyType.INFO,
        NotificationLevel.SUCCESS: apprise.NotifyType.SUCCESS,
        NotificationLevel.WARNING: apprise.NotifyType.WARNING,
        NotificationLevel.ERROR: apprise.NotifyType.FAILURE,
        NotificationLevel.CRITICAL: apprise.NotifyType.FAILURE,
    }
    
    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        timeout: float = 10.0,
        enabled_slack: bool = True,
        enabled_discord: bool = True
    ):
        self.apprise = apprise.Apprise()

        slack_url = slack_webhook_url or settings.slack_webhook_url
        discord_url = discord_webhook_url or settings.discord_webhook_url

        if slack_url and enabled_slack:
            self.apprise.add(slack_url)
            logger.info("Slack notification configured")

        if discord_url and enabled_discord:
            self.apprise.add(discord_url)
            logger.info("Discord notification configured")
        
        if not self.is_configured():
            logger.warning("No notification services configured - notifications will be skipped")
    
    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        title: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None
    ) -> bool:
        if not self.is_configured():
            logger.debug("No notification services configured, skipping notification")
            return False
        
        try:
            full_message = message
            if fields:
                full_message += "\n\n" + "\n".join([f"**{k}:** {v}" for k, v in fields.items()])
            
            notify_type = self.LEVEL_MAP.get(level, apprise.NotifyType.INFO)
            final_title = title or "AutoStack"
            
            logger.info(f"Sending {level.value} notification: {final_title}")
            
            result = await asyncio.to_thread(
                self.apprise.notify,
                body=full_message,
                title=final_title,
                notify_type=notify_type
            )
            
            if result:
                logger.info(f"Notification sent successfully: {final_title}")
            else:
                logger.warning(f"Notification failed to send: {final_title}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return False
    
    async def send_pull_request_created(
        self,
        project_name: str,
        pr_number: int,
        pr_url: str,
        pr_title: str,
        branch: str
    ) -> bool:
        """Send notification about PR creation"""
        message = f"Pull Request #{pr_number} created\n\n**Title:** {pr_title}\n**Branch:** {branch}"
        return await self.send_notification(
            message=message,
            level=NotificationLevel.SUCCESS,
            title=f"[{project_name}] PR Created",
            fields={"View PR": pr_url}
        )
    
    async def send_workflow_started(
        self,
        project_name: str,
        project_id: str
    ) -> bool:
        """Send notification about workflow start"""
        return await self.send_notification(
            message=f"Workflow started for project: {project_name}",
            level=NotificationLevel.INFO,
            title="AutoStack Workflow Started",
            fields={"Project ID": project_id[:8]}
        )
    
    async def send_workflow_completed(
        self,
        project_name: str,
        project_id: str,
        repository_url: Optional[str] = None
    ) -> bool:
        """Send notification about workflow completion"""
        fields = {"Project ID": project_id[:8]}
        if repository_url:
            fields["Repository"] = repository_url
        return await self.send_notification(
            message=f"Workflow completed successfully for project: {project_name}",
            level=NotificationLevel.SUCCESS,
            title="AutoStack Workflow Complete",
            fields=fields
        )
    
    async def send_workflow_failed(
        self,
        project_name: str,
        project_id: str,
        error: str
    ) -> bool:
        """Send notification about workflow failure"""
        return await self.send_notification(
            message=f"Workflow failed for project: {project_name}\n\n**Error:** {error[:200]}",
            level=NotificationLevel.ERROR,
            title="AutoStack Workflow Failed",
            fields={"Project ID": project_id[:8]}
        )
    
    def is_configured(self) -> bool:
        return len(self.apprise) > 0
