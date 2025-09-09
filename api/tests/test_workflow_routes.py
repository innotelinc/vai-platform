"""
Tests for workflow API routes.

This module tests the create, update, get, and validate workflow endpoints.
The fixtures for database setup, test client, and utilities are in conftest.py.
"""

import pytest
from fastapi import status


@pytest.fixture
def sample_workflow_definition():
    """Sample workflow definition for testing."""
    return {
        "nodes": [
            {
                "id": "6581",
                "type": "startCall",
                "position": {"x": 427, "y": 23},
                "data": {
                    "prompt": "Hello, I am Abhishek from Dograh. ",
                    "is_static": True,
                    "name": "Start Call",
                    "is_start": True,
                    "invalid": False,
                    "validationMessage": None,
                    "allow_interrupt": False,
                },
                "measured": {"width": 300, "height": 100},
                "selected": True,
                "dragging": False,
            },
            {
                "id": "915",
                "type": "agentNode",
                "position": {"x": 305, "y": 340},
                "data": {
                    "prompt": "You are a voice agent whose mode of speaking is voice. Ask the user whether they want to talk to a sales guy or a customer service agent.",
                    "name": "Agent",
                    "invalid": False,
                    "validationMessage": None,
                    "allow_interrupt": False,
                },
                "measured": {"width": 300, "height": 100},
                "selected": False,
                "dragging": False,
            },
            {
                "id": "7598",
                "type": "agentNode",
                "position": {"x": 90, "y": 650},
                "data": {
                    "prompt": "You are a customer service agent whose mode of communication with the user is voice. Tell them that someone from our team will reach out to them soon",
                    "name": "Agent",
                    "invalid": False,
                    "validationMessage": None,
                    "allow_interrupt": True,
                },
                "measured": {"width": 300, "height": 100},
                "selected": False,
                "dragging": False,
            },
            {
                "id": "6919",
                "type": "agentNode",
                "position": {"x": 520, "y": 650},
                "data": {
                    "prompt": "You are a sales representative whose mode of communication with the user is voice. Tell the user that someone from our team will reach out to you soon",
                    "name": "Agent",
                    "invalid": False,
                    "validationMessage": None,
                    "allow_interrupt": True,
                },
                "measured": {"width": 300, "height": 100},
                "selected": False,
                "dragging": False,
            },
            {
                "id": "1802",
                "type": "endCall",
                "position": {"x": 305, "y": 960},
                "data": {
                    "prompt": "Thank you!",
                    "invalid": False,
                    "validationMessage": None,
                    "is_static": True,
                    "name": "End Call",
                    "is_end": True,
                    "allow_interrupt": False,
                },
                "measured": {"width": 300, "height": 100},
                "selected": False,
                "dragging": False,
            },
        ],
        "edges": [
            {
                "animated": True,
                "type": "custom",
                "source": "915",
                "target": "7598",
                "id": "xy-edge__915-7598",
                "selected": False,
                "data": {
                    "condition": "The customer wants to talk to a customer service agent",
                    "label": "customer service agent",
                    "invalid": False,
                    "validationMessage": None,
                },
            },
            {
                "animated": True,
                "type": "custom",
                "source": "915",
                "target": "6919",
                "id": "xy-edge__915-6919",
                "selected": False,
                "data": {
                    "condition": "customer wants to talk to a sales representative",
                    "label": "sales representative",
                    "invalid": False,
                    "validationMessage": None,
                },
            },
            {
                "animated": True,
                "type": "custom",
                "source": "6581",
                "target": "915",
                "id": "xy-edge__6581-915",
                "selected": False,
                "data": {
                    "condition": "Always take this route",
                    "label": "Always take this route",
                    "invalid": False,
                    "validationMessage": None,
                },
            },
            {
                "animated": True,
                "type": "custom",
                "source": "7598",
                "target": "1802",
                "id": "xy-edge__7598-1802",
                "selected": False,
                "data": {
                    "condition": "end call",
                    "label": "end call",
                    "invalid": False,
                    "validationMessage": None,
                },
            },
            {
                "animated": True,
                "type": "custom",
                "source": "6919",
                "target": "1802",
                "id": "xy-edge__6919-1802",
                "selected": False,
                "data": {
                    "condition": "end call",
                    "label": "end call",
                    "invalid": False,
                    "validationMessage": None,
                },
            },
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


class TestCreateWorkflow:
    """Test cases for creating workflows."""

    async def test_create_workflow_success(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test successful workflow creation."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_create_success"
        )

        request_data = {
            "name": "Test Workflow",
            "workflow_definition": sample_workflow_definition,
        }

        async with test_client_factory(test_user) as client:
            response = await client.post("/api/v1/workflow/create", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "id" in data
            assert data["name"] == "Test Workflow"
            assert data["workflow_definition"] == sample_workflow_definition
            assert "created_at" in data
            assert "current_definition_id" in data

    async def test_create_workflow_invalid_definition(
        self, test_client_factory, db_session
    ):
        """Test workflow creation with invalid definition."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_invalid_def"
        )

        request_data = {
            "name": "Invalid Workflow",
            "workflow_definition": {"invalid": "structure"},
        }

        async with test_client_factory(test_user) as client:
            response = await client.post("/api/v1/workflow/create", json=request_data)

            # The API should still create the workflow even with invalid definition
            # Validation happens in the validate endpoint
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_create_workflow_missing_name(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test workflow creation without name."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_missing_name"
        )

        request_data = {"workflow_definition": sample_workflow_definition}

        async with test_client_factory(test_user) as client:
            response = await client.post("/api/v1/workflow/create", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_workflow_missing_definition(
        self, test_client_factory, db_session
    ):
        """Test workflow creation without workflow definition."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_missing_definition"
        )

        request_data = {"name": "Test Workflow"}

        async with test_client_factory(test_user) as client:
            response = await client.post("/api/v1/workflow/create", json=request_data)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetWorkflows:
    """Test cases for fetching workflows."""

    @pytest.mark.asyncio
    async def test_get_all_workflows_empty(self, test_client_factory, db_session):
        """Test getting all workflows when none exist."""
        # Create a test user within the test function
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_empty_workflows"
        )

        # Create a test client for this specific user
        async with test_client_factory(test_user) as client:
            response = await client.get("/api/v1/workflow/fetch")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_all_workflows_with_data(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test getting all workflows when some exist."""
        # Create a test user within the test function
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_with_workflows"
        )

        # Create a test client for this specific user
        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Test Workflow 1",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK

            # Create another workflow
            create_response2 = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Test Workflow 2",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response2.status_code == status.HTTP_200_OK

            # Get all workflows
            response = await client.get("/api/v1/workflow/fetch")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

            # Check that both workflows are returned
            workflow_names = [w["name"] for w in data]
            assert "Test Workflow 1" in workflow_names
            assert "Test Workflow 2" in workflow_names

    @pytest.mark.asyncio
    async def test_get_specific_workflow(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test getting a specific workflow by ID."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_specific_workflow"
        )

        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Specific Workflow",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            created_workflow = create_response.json()
            workflow_id = created_workflow["id"]

            # Get the specific workflow
            response = await client.get(
                f"/api/v1/workflow/fetch?workflow_id={workflow_id}"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["id"] == workflow_id
            assert data["name"] == "Specific Workflow"
            assert data["workflow_definition"] == sample_workflow_definition

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, test_client_factory, db_session):
        """Test getting a workflow that doesn't exist."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_nonexistent"
        )

        async with test_client_factory(test_user) as client:
            response = await client.get("/api/v1/workflow/fetch?workflow_id=99999")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()


class TestUpdateWorkflow:
    """Test cases for updating workflows."""

    @pytest.mark.asyncio
    async def test_update_workflow_name_only(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test updating only the workflow name."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_update_name"
        )

        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Original Name",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            workflow_id = create_response.json()["id"]

            # Update the workflow name
            update_data = {"name": "Updated Name"}
            response = await client.put(
                f"/api/v1/workflow/{workflow_id}", json=update_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["id"] == workflow_id
            assert data["name"] == "Updated Name"
            assert (
                data["workflow_definition"] == sample_workflow_definition
            )  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_update_workflow_name_and_definition(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test updating both workflow name and definition."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_update_both"
        )

        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Original Name",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            workflow_id = create_response.json()["id"]

            # Create new workflow definition
            new_definition = {
                "nodes": [
                    {
                        "id": "start",
                        "type": "start",
                        "position": {"x": 50, "y": 50},
                        "data": {"label": "New Start"},
                    }
                ],
                "edges": [],
            }

            # Update the workflow
            update_data = {
                "name": "Updated Name",
                "workflow_definition": new_definition,
            }
            response = await client.put(
                f"/api/v1/workflow/{workflow_id}", json=update_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["id"] == workflow_id
            assert data["name"] == "Updated Name"
            assert data["workflow_definition"] == new_definition

    @pytest.mark.asyncio
    async def test_update_nonexistent_workflow(self, test_client_factory, db_session):
        """Test updating a workflow that doesn't exist."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_update_nonexistent"
        )

        update_data = {"name": "Updated Name"}
        async with test_client_factory(test_user) as client:
            response = await client.put("/api/v1/workflow/99999", json=update_data)

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_workflow_missing_name(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test updating a workflow without providing a name."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_update_missing_name"
        )

        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Original Name",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            workflow_id = create_response.json()["id"]

            # Try to update without providing name
            update_data = {"workflow_definition": sample_workflow_definition}
            response = await client.put(
                f"/api/v1/workflow/{workflow_id}", json=update_data
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestWorkflowValidation:
    """Test cases for workflow validation endpoint."""

    @pytest.mark.asyncio
    async def test_validate_workflow_success(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test successful workflow validation."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_validate_success"
        )

        async with test_client_factory(test_user) as client:
            # Create a workflow first
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Valid Workflow",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            workflow_id = create_response.json()["id"]

            # Validate the workflow
            response = await client.post(f"/api/v1/workflow/{workflow_id}/validate")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["is_valid"] is True
            assert data["errors"] == []

    @pytest.mark.asyncio
    async def test_validate_nonexistent_workflow(self, test_client_factory, db_session):
        """Test validating a workflow that doesn't exist."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_validate_nonexistent"
        )

        async with test_client_factory(test_user) as client:
            response = await client.post("/api/v1/workflow/99999/validate")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()


class TestWorkflowIntegration:
    """Integration tests for workflow operations."""

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle(
        self, test_client_factory, db_session, sample_workflow_definition
    ):
        """Test the complete lifecycle of a workflow: create, get, update, validate."""
        # Create a test user for this test
        test_user = await db_session.get_or_create_user_by_provider_id(
            "test_user_lifecycle"
        )

        async with test_client_factory(test_user) as client:
            # 1. Create workflow
            create_response = await client.post(
                "/api/v1/workflow/create",
                json={
                    "name": "Lifecycle Test Workflow",
                    "workflow_definition": sample_workflow_definition,
                },
            )
            assert create_response.status_code == status.HTTP_200_OK
            workflow_id = create_response.json()["id"]

            # 2. Get the created workflow
            get_response = await client.get(
                f"/api/v1/workflow/fetch?workflow_id={workflow_id}"
            )
            assert get_response.status_code == status.HTTP_200_OK
            workflow_data = get_response.json()
            assert workflow_data["name"] == "Lifecycle Test Workflow"

            # 3. Add a new node in the workflow definition
            new_node = {
                "id": "6919_new",
                "type": "agentNode",
                "position": {"x": 520, "y": 650},
                "data": {
                    "prompt": "Something new",
                    "name": "Agent",
                    "invalid": False,
                    "validationMessage": None,
                    "allow_interrupt": True,
                },
                "measured": {"width": 300, "height": 100},
                "selected": False,
                "dragging": False,
            }
            new_edges = [
                {
                    "source": "6919",
                    "target": "6919_new",
                    "id": "xy-edge__6919-6919_new",
                    "data": {
                        "condition": "Always take this route",
                        "label": "Always take this route",
                        "invalid": False,
                        "validationMessage": None,
                    },
                },
                {
                    "source": "6919_new",
                    "target": "1802",
                    "id": "xy-edge__6919_new-1802",
                    "data": {
                        "condition": "Always take this route",
                        "label": "Always take this route",
                        "invalid": False,
                        "validationMessage": None,
                    },
                },
            ]
            new_definition = {
                "nodes": [
                    *sample_workflow_definition["nodes"],
                    new_node,
                ],
                "edges": [
                    *sample_workflow_definition["edges"],
                    *new_edges,
                ],
            }

            update_response = await client.put(
                f"/api/v1/workflow/{workflow_id}",
                json={
                    "name": "Updated Lifecycle Workflow",
                    "workflow_definition": new_definition,
                },
            )
            assert update_response.status_code == status.HTTP_200_OK
            assert update_response.json()["name"] == "Updated Lifecycle Workflow"

            # 4. Validate the updated workflow
            validate_response = await client.post(
                f"/api/v1/workflow/{workflow_id}/validate"
            )
            assert validate_response.status_code == status.HTTP_200_OK
            assert validate_response.json()["is_valid"] is True

            # 5. Verify the update by getting the workflow again
            final_get_response = await client.get(
                f"/api/v1/workflow/fetch?workflow_id={workflow_id}"
            )
            assert final_get_response.status_code == status.HTTP_200_OK
            final_data = final_get_response.json()
            assert final_data["name"] == "Updated Lifecycle Workflow"
            assert final_data["workflow_definition"] == new_definition
