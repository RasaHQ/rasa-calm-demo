import logging
from typing import Any

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.constants import CUSTOM_EMAIL_CONTENT
from app.sr_core.services import get_self_scheduling_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionGetEmailTemplate(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_get_email_template"

    @module_monitor("schedule_interview", "action_get_email_template")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metadata = get_user_metadata(tracker)
        logger.debug(f"action get email template: metadata {metadata}")
        context = get_context(metadata)
        self_scheduling_service = get_self_scheduling_service()
        email_template = await self_scheduling_service.get_invitation_email_template(
            email_style="FRIENDLY", message_channel="EMAIL", context=context
        )
        if email_template is None or email_template.content is None:
            logger.warning("No email template or template content found, we use custom email template")
            return [
                SlotSet("email_subject", CUSTOM_EMAIL_CONTENT.subject),
                SlotSet("email_body", CUSTOM_EMAIL_CONTENT.content),
            ]
        return [
            SlotSet("email_subject", email_template.content.subject),
            SlotSet("email_body", email_template.content.content),
        ]
