import unittest

from pipecat.frames.frames import (
    FunctionCallInProgressFrame,
    LLMFullResponseStartFrame,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.google.llm import (
    GoogleAssistantContextAggregator,
    GoogleLLMContext,
)
from pipecat.services.openai.llm import OpenAIAssistantContextAggregator


class TestReorderOpenAIAssistantContextAggregator(unittest.IsolatedAsyncioTestCase):
    async def test_reorder_function_messages_openai(self):
        """Ensure that after a text aggregation the function-call messages are moved
        to appear immediately after the text response, maintaining chronological
        order (assistant text -> function call -> tool response).
        """

        context = OpenAILLMContext()
        aggregator = OpenAIAssistantContextAggregator(context)

        # Simulate the start of an LLM response so that the aggregator creates a
        # response session ID that is later used for re-ordering.
        await aggregator._handle_llm_start(LLMFullResponseStartFrame())

        # Simulate the model emitting a function call which the aggregator will
        # record for potential re-ordering.
        await aggregator._handle_function_call_in_progress(
            FunctionCallInProgressFrame(
                function_name="get_weather",
                tool_call_id="1",
                arguments={},
            )
        )

        # Now push the textual part of the assistant response. This should
        # trigger the re-ordering so that the two function-related messages
        # appear *after* this text.
        await aggregator.handle_aggregation("Hello!")

        messages = context.get_messages()

        # We expect exactly three messages after re-ordering.
        self.assertEqual(len(messages), 3)

        # 1. Assistant text
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["content"], "Hello!")

        # 2. Assistant function-call message
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("tool_calls", messages[1])

        # 3. Tool response
        self.assertEqual(messages[2]["role"], "tool")
        self.assertEqual(messages[2]["tool_call_id"], "1")


class TestReorderGoogleAssistantContextAggregator(unittest.IsolatedAsyncioTestCase):
    async def test_reorder_function_messages_google(self):
        context = GoogleLLMContext()
        aggregator = GoogleAssistantContextAggregator(context)

        # Start an LLM response session.
        await aggregator._handle_llm_start(LLMFullResponseStartFrame())

        # Emit a function call.
        await aggregator._handle_function_call_in_progress(
            FunctionCallInProgressFrame(
                function_name="get_weather",
                tool_call_id="1",
                arguments={},
            )
        )

        # Push the textual content.
        await aggregator.handle_aggregation("Hello!")

        messages = context.messages  # Google context stores Content objects.

        self.assertEqual(len(messages), 3)

        # The first message should be the model text.
        first_msg = messages[0].to_json_dict()
        self.assertEqual(first_msg["role"], "model")
        self.assertEqual(first_msg["parts"][0]["text"], "Hello!")

        # The second message contains the function call (also from the model).
        second_msg = messages[1].to_json_dict()
        self.assertEqual(second_msg["role"], "model")
        self.assertIn("function_call", second_msg["parts"][0])

        # The third message is the placeholder function response.
        third_msg = messages[2].to_json_dict()
        self.assertEqual(third_msg["role"], "user")
        self.assertIn("function_response", third_msg["parts"][0])
