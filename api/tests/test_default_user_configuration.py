import os
import uuid

import pytest

from api.db.user_client import UserClient
from api.services.configuration.registry import ServiceProviders


@pytest.mark.asyncio
async def test_default_configuration_created(db_session):
    # Set env variable for openai to simulate availability of default key
    os.environ["OPENAI_API_KEY"] = "sk-test-openai-key"

    # Ensure deepgram env variable absent to focus test
    os.environ.pop("DEEPGRAM_API_KEY", None)

    # Generate a unique (random) provider user ID for each test run
    test_provider_user_id = f"provider_user_{uuid.uuid4().hex}"
    user_client: UserClient = db_session  # db_session fixture yields the client

    user_model = await user_client.get_or_create_user_by_provider_id(
        test_provider_user_id
    )

    config = await user_client.get_user_configurations(user_model.id)

    assert config.llm is not None, "LLM config should be created when env key present"
    assert config.llm.provider == ServiceProviders.OPENAI
    assert config.llm.api_key == "sk-test-openai-key"

    # Cleanup / restore env variable side-effects
    os.environ.pop("OPENAI_API_KEY", None)
