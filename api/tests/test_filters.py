"""Test filter functionality."""

from unittest.mock import MagicMock

from api.db.filters import ATTRIBUTE_FIELD_MAPPING, apply_workflow_run_filters


def test_attribute_field_mapping():
    """Test that all required attributes are mapped."""
    expected_attributes = [
        "dateRange",
        "dispositionCode",
        "duration",
        "status",
        "tokenUsage",
        "runId",
        "workflowId",
        "callTags",
        "phoneNumber",
    ]

    for attr in expected_attributes:
        assert attr in ATTRIBUTE_FIELD_MAPPING, f"Missing mapping for {attr}"


def test_filter_with_explicit_type():
    """Test that filters work with explicit type from UI."""

    # Mock query
    mock_query = MagicMock()
    mock_query.where = MagicMock(return_value=mock_query)

    test_cases = [
        # Date range filter
        {
            "filters": [
                {
                    "attribute": "dateRange",
                    "type": "dateRange",
                    "value": {"from": "2024-01-01", "to": "2024-01-31"},
                }
            ],
        },
        # Multi-select filter
        {
            "filters": [
                {
                    "attribute": "dispositionCode",
                    "type": "multiSelect",
                    "value": {"codes": ["XFER", "HU"]},
                }
            ],
        },
        # Number range filter
        {
            "filters": [
                {
                    "attribute": "duration",
                    "type": "numberRange",
                    "value": {"min": 60, "max": 300},
                }
            ],
        },
        # Radio/status filter
        {
            "filters": [
                {
                    "attribute": "status",
                    "type": "radio",
                    "value": {"status": "completed"},
                }
            ],
        },
        # Number filter
        {
            "filters": [
                {"attribute": "runId", "type": "number", "value": {"value": 123}}
            ],
        },
        # Text filter
        {
            "filters": [
                {
                    "attribute": "phoneNumber",
                    "type": "text",
                    "value": {"value": "+1234567890"},
                }
            ],
        },
        # Tags filter
        {
            "filters": [
                {
                    "attribute": "callTags",
                    "type": "tags",
                    "value": {"codes": ["tag1", "tag2"]},
                }
            ],
        },
    ]

    for test_case in test_cases:
        result = apply_workflow_run_filters(mock_query, test_case["filters"])
        # The function should process the filter without errors
        assert result is not None


def test_filter_format_with_type():
    """Test that filters work with attribute, type, and value."""

    mock_query = MagicMock()
    mock_query.where = MagicMock(return_value=mock_query)

    # Test with various filter combinations
    filters = [
        {
            "attribute": "dispositionCode",
            "type": "multiSelect",
            "value": {"codes": ["NIBP"]},
        },
        {
            "attribute": "duration",
            "type": "numberRange",
            "value": {"min": 0, "max": 60},
        },
        {"attribute": "phoneNumber", "type": "text", "value": {"value": "555"}},
    ]

    result = apply_workflow_run_filters(mock_query, filters)

    # Should have called where() for applying filters
    assert mock_query.where.called
    assert result is not None


def test_unknown_attribute_ignored():
    """Test that unknown attributes are safely ignored."""

    mock_query = MagicMock()
    mock_query.where = MagicMock(return_value=mock_query)

    filters = [
        {"attribute": "unknownAttribute", "value": {"value": "test"}},
        {"attribute": "dispositionCode", "value": {"codes": ["XFER"]}},
    ]

    result = apply_workflow_run_filters(mock_query, filters)

    # Should still process the valid filter
    assert result is not None


def test_empty_filters():
    """Test that empty filters return the query unchanged."""

    mock_query = MagicMock()

    result = apply_workflow_run_filters(mock_query, None)
    assert result == mock_query

    result = apply_workflow_run_filters(mock_query, [])
    assert result == mock_query
