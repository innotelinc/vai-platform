from unittest.mock import Mock

import pytest

from api.services.workflow.pipecat_engine import PipecatEngine
from api.services.workflow.workflow import WorkflowGraph


class TestPipecatEngine:
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for PipecatEngine initialization."""
        return {
            "task": Mock(),
            "llm": Mock(),
            "context": Mock(),
            "tts": Mock(),
            "transport": Mock(),
            "workflow": Mock(spec=WorkflowGraph),
            "call_context_vars": {},
        }

    @pytest.fixture
    def engine_with_context(self, mock_dependencies):
        """Create a PipecatEngine instance with test context variables."""
        context_vars = {
            "first_name": "John",
            "last_name": "Doe",
            "age": 25,
            "email": "john.doe@example.com",
            "empty_var": "",
            "zero_var": 0,
            "false_var": False,
        }
        mock_dependencies["call_context_vars"] = context_vars
        return PipecatEngine(**mock_dependencies)

    @pytest.fixture
    def engine_empty_context(self, mock_dependencies):
        """Create a PipecatEngine instance with empty context variables."""
        mock_dependencies["call_context_vars"] = {}
        return PipecatEngine(**mock_dependencies)

    def test_format_prompt_simple_variable_replacement(self, engine_with_context):
        """Test simple variable replacement without filters."""
        prompt = "Hello {{ first_name }}, welcome!"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John, welcome!"

    def test_format_prompt_multiple_variables(self, engine_with_context):
        """Test multiple variable replacements in a single prompt."""
        prompt = "Hello {{ first_name }} {{ last_name }}, you are {{ age }} years old."
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John Doe, you are 25 years old."

    def test_format_prompt_with_fallback_existing_value(self, engine_with_context):
        """Test fallback filter when value exists."""
        prompt = "Hello {{ first_name | fallback }}, nice to meet you!"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John, nice to meet you!"

    def test_format_prompt_with_fallback_missing_value(self, engine_empty_context):
        """Test fallback filter when value is missing."""
        prompt = "Hello {{ first_name | fallback }}, nice to meet you!"
        result = engine_empty_context._format_prompt(prompt)
        assert result == "Hello First_Name, nice to meet you!"

    def test_format_prompt_with_custom_fallback_missing_value(
        self, engine_empty_context
    ):
        """Test fallback filter with custom fallback value when variable is missing."""
        prompt = "Hello {{ first_name | fallback:Guest }}, welcome!"
        result = engine_empty_context._format_prompt(prompt)
        assert result == "Hello Guest, welcome!"

    def test_format_prompt_with_custom_fallback_existing_value(
        self, engine_with_context
    ):
        """Test fallback filter with custom fallback value when variable exists."""
        prompt = "Hello {{ first_name | fallback:Guest }}, welcome!"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John, welcome!"

    def test_format_prompt_empty_string_variable(self, engine_with_context):
        """Test variable with empty string value."""
        prompt = "Value: '{{ empty_var | fallback:No Value }}'"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Value: 'No Value'"

    def test_format_prompt_zero_value(self, engine_with_context):
        """Test variable with zero value (should not trigger fallback)."""
        prompt = "Count: {{ zero_var | fallback:None }}"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Count: 0"

    def test_format_prompt_false_value(self, engine_with_context):
        """Test variable with False value (should not trigger fallback)."""
        prompt = "Status: {{ false_var | fallback:Unknown }}"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Status: False"

    def test_format_prompt_missing_variable_no_fallback(self, engine_empty_context):
        """Test missing variable without fallback filter."""
        prompt = "Hello {{ missing_var }}, welcome!"
        result = engine_empty_context._format_prompt(prompt)
        assert result == "Hello , welcome!"

    def test_format_prompt_complex_mixed_scenario(self, engine_with_context):
        """Test complex scenario with multiple variables, some with fallbacks."""
        prompt = (
            "Dear {{ first_name | fallback:Customer }}, "
            "your email {{ email }} is confirmed. "
            "{{ missing_info | fallback:Additional information }} will be sent later. "
            "You are {{ age }} years old."
        )
        result = engine_with_context._format_prompt(prompt)
        expected = (
            "Dear John, "
            "your email john.doe@example.com is confirmed. "
            "Additional information will be sent later. "
            "You are 25 years old."
        )
        assert result == expected

    def test_format_prompt_whitespace_handling(self, engine_with_context):
        """Test handling of whitespace in template variables."""
        prompt = "Hello {{  first_name  |  fallback  :  Default  }}, welcome!"
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John, welcome!"

    def test_format_prompt_no_variables(self, engine_with_context):
        """Test prompt with no template variables."""
        prompt = "This is a regular prompt with no variables."
        result = engine_with_context._format_prompt(prompt)
        assert result == "This is a regular prompt with no variables."

    def test_format_prompt_empty_prompt(self, engine_with_context):
        """Test empty prompt."""
        prompt = ""
        result = engine_with_context._format_prompt(prompt)
        assert result == ""

    def test_format_prompt_none_prompt(self, engine_with_context):
        """Test None prompt."""
        prompt = None
        result = engine_with_context._format_prompt(prompt)
        assert result is None

    def test_format_prompt_nested_braces(self, engine_with_context):
        """Test handling of nested or malformed braces."""
        prompt = "Hello {{ first_name }}, this {is not a template} variable."
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello John, this {is not a template} variable."

    def test_format_prompt_special_characters_in_value(self):
        """Test variables containing special characters."""
        mock_deps = {
            "task": Mock(),
            "llm": Mock(),
            "context": Mock(),
            "tts": Mock(),
            "transport": Mock(),
            "workflow": Mock(spec=WorkflowGraph),
            "call_context_vars": {
                "special_name": "John & Jane's Company",
                "email": "test@domain.com",
            },
        }
        engine = PipecatEngine(**mock_deps)

        prompt = "Company: {{ special_name }}, Contact: {{ email }}"
        result = engine._format_prompt(prompt)
        assert result == "Company: John & Jane's Company, Contact: test@domain.com"

    def test_format_prompt_numeric_and_boolean_conversion(self):
        """Test conversion of different data types to strings."""
        mock_deps = {
            "task": Mock(),
            "llm": Mock(),
            "context": Mock(),
            "tts": Mock(),
            "transport": Mock(),
            "workflow": Mock(spec=WorkflowGraph),
            "call_context_vars": {
                "count": 42,
                "price": 99.99,
                "is_active": True,
                "items": ["apple", "banana"],
            },
        }
        engine = PipecatEngine(**mock_deps)

        prompt = "Count: {{ count }}, Price: ${{ price }}, Active: {{ is_active }}, Items: {{ items }}"
        result = engine._format_prompt(prompt)
        assert (
            result
            == "Count: 42, Price: $99.99, Active: True, Items: ['apple', 'banana']"
        )

    def test_format_prompt_case_sensitivity(self, engine_with_context):
        """Test that variable names are case sensitive."""
        prompt = (
            "Hello {{ First_Name | fallback }}, welcome!"  # Note the capitalization
        )
        result = engine_with_context._format_prompt(prompt)
        assert result == "Hello First_Name, welcome!"  # Should use fallback
