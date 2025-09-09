import re
from typing import Any, Dict, List

import httpx
from loguru import logger

from api.db import db_client
from api.services.campaign.source_sync import CampaignSourceSyncService
from api.services.integrations.nango import NangoService


class GoogleSheetsSyncService(CampaignSourceSyncService):
    """Implementation for Google Sheets synchronization"""

    def __init__(self):
        self.nango_service = NangoService()
        self.sheets_api_base = "https://sheets.googleapis.com/v4/spreadsheets"

    async def sync_source_data(self, campaign_id: int) -> int:
        """
        Fetches data from Google Sheets and creates queued_runs
        """
        # Get campaign
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # 1. Get Google Sheets integration for the organization
        integrations = await db_client.get_integrations_by_organization_id(
            campaign.organization_id
        )
        integration = None
        for intg in integrations:
            if intg.provider == "google-sheet" and intg.is_active:
                integration = intg
                break

        if not integration:
            raise ValueError("Google Sheets integration not found or inactive")

        # 2. Get OAuth token via Nango using the integration_id (which is the Nango connection ID)
        token_data = await self.nango_service.get_access_token(
            connection_id=integration.integration_id, provider_config_key="google-sheet"
        )
        access_token = token_data["credentials"]["access_token"]

        # 3. Extract sheet ID from URL
        sheet_id = self._extract_sheet_id(campaign.source_id)

        # 4. Get sheet metadata (to find data range)
        metadata = await self._get_sheet_metadata(sheet_id, access_token)
        if not metadata.get("sheets"):
            raise ValueError("No sheets found in the spreadsheet")

        sheet_name = metadata["sheets"][0]["properties"]["title"]

        # 5. Fetch all data from sheet
        sheet_data = await self._fetch_sheet_data(
            sheet_id,
            f"{sheet_name}!A:Z",  # Get all columns A-Z
            access_token,
        )

        # 6. Convert to queued_runs
        if not sheet_data or len(sheet_data) < 2:
            logger.warning(f"No data found in sheet for campaign {campaign_id}")
            return 0

        headers = sheet_data[0]  # First row is headers
        rows = sheet_data[1:]  # Rest is data

        queued_runs = []
        for idx, row_values in enumerate(rows, 1):
            # Pad row to match headers length
            padded_row = row_values + [""] * (len(headers) - len(row_values))

            # Create context variables dict
            context_vars = dict(zip(headers, padded_row))

            # Skip if no phone number
            if not context_vars.get("phone_number"):
                logger.debug(f"Skipping row {idx}: no phone_number")
                continue

            # Generate unique source UUID
            source_uuid = f"sheet_{sheet_id}_row_{idx}"

            queued_runs.append(
                {
                    "campaign_id": campaign_id,
                    "source_uuid": source_uuid,
                    "context_variables": context_vars,
                    "state": "queued",
                }
            )

        # 7. Bulk insert
        if queued_runs:
            await db_client.bulk_create_queued_runs(queued_runs)
            logger.info(
                f"Created {len(queued_runs)} queued runs for campaign {campaign_id}"
            )

        # 8. Update campaign total_rows
        await db_client.update_campaign(
            campaign_id=campaign_id,
            total_rows=len(queued_runs),
            source_sync_status="completed",
        )

        return len(queued_runs)

    async def _fetch_sheet_data(
        self, sheet_id: str, range: str, access_token: str
    ) -> List[List[str]]:
        """Fetch data from Google Sheets API"""
        url = f"{self.sheets_api_base}/{sheet_id}/values/{range}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            return data.get("values", [])

    async def _get_sheet_metadata(
        self, sheet_id: str, access_token: str
    ) -> Dict[str, Any]:
        """Get sheet metadata including sheet names"""
        url = f"{self.sheets_api_base}/{sheet_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        logger.debug(f"Fetching sheet metadata from URL: {url}")
        logger.debug(f"Using sheet_id: {sheet_id}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for URL: {url}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error fetching sheet metadata: {e}")
                raise

    def _extract_sheet_id(self, sheet_url: str) -> str:
        """
        Extract sheet ID from various Google Sheets URL formats:
        - https://docs.google.com/spreadsheets/d/{id}/edit
        - https://docs.google.com/spreadsheets/d/{id}/edit#gid=0
        """
        pattern = r"/spreadsheets/d/([a-zA-Z0-9-_]+)"
        match = re.search(pattern, sheet_url)
        if match:
            return match.group(1)
        raise ValueError(f"Invalid Google Sheets URL: {sheet_url}")

    async def validate_source_schema(self, source_config: Dict[str, Any]) -> bool:
        """Validate that required columns exist"""
        required_columns = ["phone_number", "first_name", "last_name"]

        # Fetch just the header row
        sheet_id = self._extract_sheet_id(source_config["source_id"])
        access_token = source_config["access_token"]

        headers = await self._fetch_sheet_data(
            sheet_id,
            "A1:Z1",  # Just first row
            access_token,
        )

        if not headers:
            return False

        header_row = headers[0]
        return all(col in header_row for col in required_columns)
