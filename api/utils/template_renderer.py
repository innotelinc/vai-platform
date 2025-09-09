"""Common template rendering utility."""

import re
from typing import Any, Dict


def render_template(template_str: str, template_var_mapping: Dict[str, Any]) -> str:  # noqa: C901 – complex but self-contained
    """Replace template placeholders in *template_str* with values from *template_var_mapping*.

    Supported syntax:
    * ``{{ variable_name }}``
    * ``{{ variable_name | fallback }}``
    * ``{{ variable_name | fallback:default_value }}``

    If the variable is undefined and a *fallback* filter is specified the value
    of *default_value* (or the *variable_name* itself if no default is given)
    is used instead.
    """

    if not template_str:
        return template_str

    # Regex matches e.g. ``{{ name }}``, ``{{ name | fallback }}``, ``{{ name | fallback:John }}``
    pattern = r"\{\{\s*([^|\s}]+)(?:\s*\|\s*([^:}]+)(?::([^}]+))?)?\s*\}\}"

    def _replace(match: re.Match[str]) -> str:  # type: ignore[type-arg]
        variable_name = match.group(1).strip()
        filter_name = match.group(2).strip() if match.group(2) else None
        filter_value = match.group(3).strip() if match.group(3) else None

        # Pull value from context
        value = template_var_mapping.get(variable_name)

        # Apply filters
        if filter_name == "fallback":
            if value is None or value == "":
                # Use explicit default value or a title-cased variable name.
                value = (
                    filter_value if filter_value is not None else variable_name.title()
                )

        # Convert *None* to an empty string so that re.sub replacement works.
        return str(value) if value is not None else ""

    # Replace template variables
    result = re.sub(pattern, _replace, template_str)

    # Handle line breaks (convert literal \n to actual newlines)
    result = result.replace("\\n", "\n")

    return result
