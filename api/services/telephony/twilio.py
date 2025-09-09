import random
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
from loguru import logger
from pydantic import ValidationError
from twilio.request_validator import RequestValidator

from api.constants import (
    BACKEND_API_ENDPOINT,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_DEFAULT_FROM_NUMBER,
)
from api.db import db_client


class TwilioService:
    """Service for interacting with Twilio API."""

    def __init__(self):
        if (
            not TWILIO_DEFAULT_FROM_NUMBER
            or not TWILIO_ACCOUNT_SID
            or not TWILIO_AUTH_TOKEN
        ):
            raise ValidationError(
                "Please set TWILIO_DEFAULT_FROM_NUMBER, TWILIO_ACCOUNT_SID, and TWILIO_AUTH_TOKEN environment"
                "variables to use TwilioService"
            )

        self.account_sid = TWILIO_ACCOUNT_SID
        self.auth_token = TWILIO_AUTH_TOKEN
        self.default_from_number = TWILIO_DEFAULT_FROM_NUMBER

        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"

    async def get_organization_phone_numbers(self, organization_id: int) -> List[str]:
        """
        Get the list of Twilio phone numbers configured for an organization.

        Args:
            organization_id: The organization ID

        Returns:
            List of phone numbers, or default if none configured
        """
        try:
            from api.enums import OrganizationConfigurationKey

            config = await db_client.get_configuration(
                organization_id,
                OrganizationConfigurationKey.TWILIO_PHONE_NUMBERS.value,
            )

            if config and config.value:
                # Expect the value to be a list of phone numbers
                phone_numbers = config.value.get("value", [])
                if isinstance(phone_numbers, list) and phone_numbers:
                    return phone_numbers
        except Exception as e:
            logger.warning(
                f"Error getting phone numbers for org {organization_id}: {e}"
            )

        # Fall back to default from environment
        return [self.default_from_number]

    async def initiate_call(
        self,
        to_number: str,
        url_args: Dict[str, Any] = {},
        workflow_run_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Initiates a Twilio call using the Calls API.

        Args:
            to_number: The destination phone number
            url_args: Dictionary of URL parameters to append to the base URL
            workflow_run_id: The workflow run ID for tracking callbacks
            organization_id: The organization ID for selecting phone numbers
            **kwargs: Additional parameters to pass to the Twilio API

        Returns:
            Dict containing the Twilio API response
        """
        endpoint = f"{self.base_url}/Calls.json"

        if not BACKEND_API_ENDPOINT:
            raise ValidationError(
                "Please set BACKEND_API_ENDPOINT environment variable to a tunnel or persistant URL"
            )

        # Construct the URL with parameters if any
        url: str = f"https://{BACKEND_API_ENDPOINT}/api/v1/twilio/twiml"
        if url_args:
            query_string = urlencode(url_args)
            url = f"{url}?{query_string}"

        logger.debug(f"Initiating call with URL: {url}")

        # Get phone numbers for organization and select one randomly
        if organization_id:
            phone_numbers = await self.get_organization_phone_numbers(organization_id)
            from_number = random.choice(phone_numbers)
            logger.info(
                f"Selected phone number {from_number} from {len(phone_numbers)} "
                f"available numbers for org {organization_id}"
            )
        else:
            from_number = self.default_from_number

        # Prepare call data
        data = {"To": to_number, "From": from_number, "Url": url}

        if not BACKEND_API_ENDPOINT:
            raise ValidationError(
                "Please set BACKEND_API_ENDPOINT environment variable to a tunnel or persistant URL"
            )

        # Add status callback configuration if workflow_run_id is provided
        if workflow_run_id:
            callback_url = f"https://{BACKEND_API_ENDPOINT}/api/v1/twilio/status-callback/{workflow_run_id}"
            data.update(
                {
                    "StatusCallback": callback_url,
                    "StatusCallbackEvent": [
                        "initiated",
                        "ringing",
                        "answered",
                        "completed",
                    ],
                    "StatusCallbackMethod": "POST",
                }
            )

        # Add any additional kwargs
        data.update(kwargs)

        # Make the API request
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.account_sid, self.auth_token)
            async with session.post(endpoint, data=data, auth=auth) as response:
                if response.status != 201:
                    error_data = await response.json()
                    raise Exception(f"Failed to initiate call: {error_data}")

                return await response.json()

    async def get_start_call_twiml(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        if not BACKEND_API_ENDPOINT:
            raise ValidationError(
                "Please set BACKEND_API_ENDPOINT environment variable to a tunnel or persistant URL"
            )

        twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{BACKEND_API_ENDPOINT}/api/v1/twilio/ws/{workflow_id}/{user_id}/{workflow_run_id}"></Stream>
    </Connect>
    <Pause length="40"/>
</Response>"""
        return twiml_content

    async def get_call(self, call_sid: str) -> Dict[str, Any]:
        """
        Retrieves information about a specific call.

        Args:
            call_sid: The SID of the call to retrieve

        Returns:
            Dict containing the call information
        """
        endpoint = f"{self.base_url}/Calls/{call_sid}.json"

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.account_sid, self.auth_token)
            async with session.get(endpoint, auth=auth) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise Exception(f"Failed to get call: {error_data}")

                return await response.json()

    def verify_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        """
        Verify Twilio request signature using official Twilio SDK.

        Args:
            url: The full URL of the webhook
            params: The POST parameters (form data) as a dictionary
            signature: The X-Twilio-Signature header value

        Returns:
            bool: True if signature is valid, False otherwise
        """
        validator = RequestValidator(self.auth_token)
        return validator.validate(url, params, signature)
