### - The test gets stuck. Need to figure out a way to run the test

# import asyncio
# import unittest

# from loguru import logger

# from pipecat.frames.frames import (
#     FunctionCallFromLLM,
#     FunctionCallInProgressFrame,
#     FunctionCallResultFrame,
#     FunctionCallsStartedFrame,
#     LLMFullResponseEndFrame,
#     LLMFullResponseStartFrame,
#     LLMTextFrame,
# )
# from pipecat.processors.aggregators.openai_llm_context import (
#     OpenAILLMContext,
#     OpenAILLMContextFrame,
# )
# from pipecat.processors.frame_processor import FrameDirection
# from pipecat.services.llm_service import (
#     FunctionCallParams,
#     FunctionCallResultProperties,
#     LLMService,
# )
# from pipecat.tests.utils import run_test


# class MockLLMService(LLMService):
#     """A very small mocked LLM service that, upon receiving an
#     ``OpenAILLMContextFrame``, streams a text completion followed by the
#     execution of the supplied tools (function calls).
#     """

#     def __init__(self, *, content: str, tools: list[dict[str, dict]], **kwargs):
#         # Run function calls sequentially so that frame ordering is deterministic.
#         super().__init__(run_in_parallel=False, **kwargs)
#         self._content = content
#         self._tools = tools

#     async def process_frame(self, frame, direction: FrameDirection):
#         await super().process_frame(frame, direction)

#         if isinstance(frame, OpenAILLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
#             # Simulate the start of a streamed completion.
#             await self.push_frame(LLMFullResponseStartFrame())
#             await self.push_frame(LLMTextFrame(self._content))

#             # Convert tool specs into FunctionCallFromLLM objects.
#             function_calls = []
#             for idx, tool in enumerate(self._tools):
#                 function_calls.append(
#                     FunctionCallFromLLM(
#                         function_name=tool["function_name"],
#                         tool_call_id=f"tool_{idx}",
#                         arguments=tool.get("arguments", {}),
#                         context=frame.context,
#                     )
#                 )

#             # Ask the LLM service base class to execute the calls.
#             await self.run_function_calls(function_calls)

#             # Finish the streamed response.
#             await self.push_frame(LLMFullResponseEndFrame())

#     async def _run_function_call(self, runner_item):  # type: ignore[override] – narrow signature
#         # Ensure run_llm=True so that downstream processors know they can
#         # immediately trigger another LLM call after the result is committed.
#         runner_item.run_llm = True
#         await super()._run_function_call(runner_item)


# class TestMockLLMPipeline(unittest.IsolatedAsyncioTestCase):
#     async def test_mock_llm_pipeline_with_tools(self):
#         # ------------------------------------------------------------------
#         # 1. Create mocked LLM service with completion text and tools
#         # ------------------------------------------------------------------
#         completion_text = "Hello from mocked LLM!"
#         tools = [
#             {"function_name": "tool_one", "arguments": {"a": 1}},
#             {"function_name": "tool_two", "arguments": {"b": 2}},
#         ]
#         llm = MockLLMService(content=completion_text, tools=tools)

#         # ------------------------------------------------------------------
#         # 2. Register the tool functions – they simply log & sleep briefly.
#         #    Each of them marks that it has run so that we can assert later.
#         # ------------------------------------------------------------------
#         executed: dict[str, bool] = {t["function_name"]: False for t in tools}

#         def make_handler(name: str):
#             async def _handler(params: FunctionCallParams):
#                 logger.debug(f"Executing {name} with args {params.arguments}")
#                 executed[name] = True
#                 await asyncio.sleep(0.01)
#                 await params.result_callback(
#                     {"status": "ok"},
#                     properties=FunctionCallResultProperties(run_llm=True),
#                 )

#             return _handler

#         for t in tools:
#             llm.register_function(t["function_name"], make_handler(t["function_name"]))

#         # ------------------------------------------------------------------
#         # 3. Build the pipeline and send the initial context frame that
#         #    triggers the completion.
#         # ------------------------------------------------------------------
#         context = OpenAILLMContext()
#         context.add_message({"role": "user", "content": "Hi!"})
#         frames_to_send = [OpenAILLMContextFrame(context)]

#         expected_down_frames = [
#             LLMFullResponseStartFrame,
#             LLMTextFrame,
#             FunctionCallsStartedFrame,
#             FunctionCallInProgressFrame,
#             FunctionCallResultFrame,
#             FunctionCallInProgressFrame,
#             FunctionCallResultFrame,
#             LLMFullResponseEndFrame,
#         ]

#         # Run the test pipeline.
#         received_down_frames, _ = await run_test(
#             llm,
#             frames_to_send=frames_to_send,
#             expected_down_frames=expected_down_frames,
#         )

#         # ------------------------------------------------------------------
#         # 4. Verify that both tool functions executed and that run_llm=True
#         #    in all FunctionCallResultFrame instances.
#         # ------------------------------------------------------------------
#         self.assertTrue(all(executed.values()))

#         for frame in received_down_frames:
#             if isinstance(frame, FunctionCallResultFrame):
#                 self.assertTrue(frame.run_llm)
