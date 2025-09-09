from api.utils.template_renderer import render_template


def test_render_template_basic():
    """Test basic template rendering."""
    template = "Hello {{name}}, your balance is {{balance}}."
    context = {"name": "John", "balance": "$1000"}

    result = render_template(template, context)
    assert result == "Hello John, your balance is $1000."


def test_render_template_with_spaces():
    """Test template rendering with spaces around variables."""
    template = "Hello {{ name }}, your balance is {{ balance }}."
    context = {"name": "John", "balance": "$1000"}

    result = render_template(template, context)
    assert result == "Hello John, your balance is $1000."


def test_render_template_missing_variable():
    """Test template rendering with missing variables."""
    template = "Hello {{name}}, your balance is {{balance}}."
    context = {"name": "John"}

    result = render_template(template, context)
    assert result == "Hello John, your balance is ."


def test_render_template_with_fallback():
    """Test template rendering with fallback values."""
    template = "Hello {{name | fallback}}, your balance is {{balance | fallback:$0}}."
    context = {}

    result = render_template(template, context)
    assert result == "Hello Name, your balance is $0."


def test_render_template_with_fallback_existing_value():
    """Test that fallback is not used when value exists."""
    template = "Hello {{name | fallback:Guest}}"
    context = {"name": "John"}

    result = render_template(template, context)
    assert result == "Hello John"


def test_render_template_with_line_breaks():
    """Test template rendering with line breaks."""
    template = (
        "DISPOSITION_CODE: {{call_disposition}}\\nCALL_DURATION: {{call_duration}}"
    )
    context = {"call_disposition": "XFER", "call_duration": "300"}

    result = render_template(template, context)
    expected = "DISPOSITION_CODE: XFER\nCALL_DURATION: 300"
    assert result == expected


def test_render_template_empty():
    """Test rendering empty template."""
    assert render_template("", {}) == ""
    assert render_template(None, {}) == None


def test_render_template_no_placeholders():
    """Test template with no placeholders."""
    template = "This is a plain text message"
    result = render_template(template, {"unused": "value"})
    assert result == "This is a plain text message"


def test_render_template_none_values():
    """Test template with None values."""
    template = "Value: {{value}}"
    context = {"value": None}

    result = render_template(template, context)
    assert result == "Value: "


def test_render_template_numeric_values():
    """Test template with numeric values."""
    template = "Count: {{count}}, Price: {{price}}"
    context = {"count": 42, "price": 19.99}

    result = render_template(template, context)
    assert result == "Count: 42, Price: 19.99"
