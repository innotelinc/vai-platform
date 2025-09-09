### - This test has some weird loop which keeps on increasing the context size

# import asyncio
# import json
# import unittest
# from types import SimpleNamespace
# from unittest import mock

# from loguru import logger

# from pipecat.frames.frames import (
#     FunctionCallInProgressFrame,
#     FunctionCallResultFrame,
#     FunctionCallsStartedFrame,
#     LLMFullResponseEndFrame,
#     LLMFullResponseStartFrame,
#     LLMGeneratedTextFrame,
#     LLMTextFrame,
# )
# from pipecat.pipeline.pipeline import Pipeline
# from pipecat.processors.aggregators.openai_llm_context import (
#     OpenAILLMContext,
#     OpenAILLMContextFrame,
# )
# from pipecat.services.llm_service import (
#     FunctionCallParams,
#     FunctionCallResultProperties,
# )
# from pipecat.services.openai.llm import OpenAILLMService
# from pipecat.tests.utils import run_test


# class _MockAsyncStream:
#     """A minimal async-stream wrapper that mimics ``openai.AsyncStream``."""

#     def __init__(self, chunks):
#         self._chunks = chunks

#     def __aiter__(self):
#         self._idx = 0
#         return self

#     async def __anext__(self):
#         if self._idx >= len(self._chunks):
#             raise StopAsyncIteration
#         item = self._chunks[self._idx]
#         self._idx += 1
#         await asyncio.sleep(0)  # Yield control
#         return item


# # ------------------------------------------------------------------
# # Factories for mock chunks
# # ------------------------------------------------------------------


# def _make_tool_call(tool_name: str, args_json: str, *, idx: int = 0):
#     function = SimpleNamespace(name=tool_name, arguments=args_json)
#     return SimpleNamespace(index=idx, id=f"call-{idx}", function=function)


# def _make_chunk(*, content: str | None = None, tool_calls=None, usage=None):
#     delta = SimpleNamespace()
#     # When we are asked to simulate multiple tool calls in parallel, OpenAI
#     # sends *separate* chunks for every tool-call index.  To mimic that behaviour
#     # in tests we split a list of tool calls (>1) into individual chunks – one
#     # for each tool call – while keeping the original single-chunk behaviour
#     # when zero or one tool calls are supplied.  This enables us to write
#     # concise tests such as ``_make_chunk(tool_calls=[call_1, call_2])`` that
#     # accurately reflect the streaming protocol.

#     # No special handling needed if there is textual content or 0/1 tool calls.
#     if content is not None or tool_calls is None or len(tool_calls) <= 1:
#         if content is not None:
#             delta.content = content
#         # Always set tool_calls so downstream code can safely access it
#         delta.tool_calls = tool_calls if tool_calls is not None else None
#         return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)

#     # --- Multiple tool calls (len(tool_calls) > 1) ---
#     # Create a list of chunks, each containing a single tool call.  This is the
#     # format produced by the OpenAI client when several tools are invoked in a
#     # single assistant response.
#     chunks = []
#     for tc in tool_calls:
#         delta_tc = SimpleNamespace(tool_calls=[tc])
#         chunks.append(SimpleNamespace(choices=[SimpleNamespace(delta=delta_tc)], usage=usage))

#     return chunks


# class TestBaseOpenAILLMService(unittest.IsolatedAsyncioTestCase):
#     async def test_process_context_with_patch(self):
#         streamed_text = "Hello from OpenAI!"
#         tool_name = "echo"
#         tool_name_2 = "echo_2"
#         tool_args = {"text": "hello"}
#         tool_args_2 = {"text": "hello_2"}

#         # Build mocked stream (tool call first, then text)
#         chunks = [
#             _make_chunk(content=streamed_text),
#             _make_chunk(tool_calls=[_make_tool_call(tool_name, json.dumps(tool_args))]),
#             _make_chunk(tool_calls=[_make_tool_call(tool_name_2, json.dumps(tool_args_2), idx=1)]),
#         ]

#         # Instantiate real OpenAILLMService (no need for actual API key)
#         llm = OpenAILLMService(model="gpt-4o-mini", api_key="test")

#         # Patch get_chat_completions to return our mocked async stream
#         async def fake_get_chat_completions(self, context, messages):  # noqa: D401
#             return _MockAsyncStream(chunks)

#         with mock.patch.object(llm.__class__, "get_chat_completions", fake_get_chat_completions):
#             # Register echo tool
#             executed = False

#             async def echo_handler(params: FunctionCallParams):
#                 nonlocal executed
#                 executed = True
#                 # sleep for 1 second
#                 logger.info("echo_handler: sleeping for 5 second")
#                 await asyncio.sleep(5)
#                 await params.result_callback(
#                     {"ok": True},
#                     properties=FunctionCallResultProperties(run_llm=True),
#                 )

#             async def echo_2_handler(params: FunctionCallParams):
#                 nonlocal executed
#                 executed = True
#                 # sleep for 1 second
#                 logger.info("echo_2_handler: sleeping for 5 second")
#                 await asyncio.sleep(5)
#                 await params.result_callback(
#                     {"ok": True},
#                     properties=FunctionCallResultProperties(run_llm=True),
#                 )

#             llm.register_function(tool_name, echo_handler)
#             llm.register_function(tool_name_2, echo_2_handler)

#             # Prepare context and send
#             context = OpenAILLMContext()
#             context.add_message({"role": "user", "content": "Hi"})
#             frames_to_send = [OpenAILLMContextFrame(context)]

#             expected_down_frames = [
#                 LLMFullResponseStartFrame,
#                 FunctionCallsStartedFrame,
#                 FunctionCallInProgressFrame,
#                 FunctionCallResultFrame,
#                 LLMGeneratedTextFrame,
#                 LLMTextFrame,
#                 LLMFullResponseEndFrame,
#             ]

#             context_aggregator = llm.create_context_aggregator(context)

#             pipeline = Pipeline([llm, context_aggregator.assistant()])

#             down_frames, _ = await run_test(
#                 pipeline,
#                 frames_to_send=frames_to_send,
#                 expected_down_frames=expected_down_frames,
#                 send_end_frame=False,
#             )

#             # Assertions
#             self.assertTrue(executed)
#             for fr in down_frames:
#                 if isinstance(fr, FunctionCallResultFrame):
#                     self.assertTrue(fr.run_llm)
#                 if isinstance(fr, LLMTextFrame):
#                     self.assertEqual(fr.text, streamed_text)


# if __name__ == "__main__":
#     unittest.main()
