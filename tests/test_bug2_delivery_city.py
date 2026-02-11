"""
Tests for BUG-2: Delivery City Not Saving on Quote Page.

Bug description:
    The Save button (showSaveConfirmation) calls saveAllItems() which only saves
    Handsontable rows, NOT the delivery_city field. The saveDeliveryCity() function
    only fires on blur/change events via an event listener on the input. When a user
    types a delivery city and clicks Save without first blurring the input, the city
    value is lost.

Fix required:
    Add saveDeliveryCity() call inside showSaveConfirmation() BEFORE saveAllItems().

Test strategy:
    These tests inspect the JavaScript source code emitted in main.py to verify
    that showSaveConfirmation includes a call to saveDeliveryCity. This follows
    the same source-inspection pattern used in test_inline_update_and_activity_log.py.
"""

import pytest
import os
import re

# Set test environment before importing app
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")


def _read_main_source():
    """Read main.py source code."""
    source_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "main.py",
    )
    with open(source_path, "r") as f:
        return f.read()


def _extract_js_function(source, func_name):
    """Extract the body of a JavaScript function from the Python source.

    Finds `function <func_name>(...)` and returns everything up to the next
    top-level `function ` or end of the Script block.
    """
    pattern = rf"function {func_name}\("
    match = re.search(pattern, source)
    if not match:
        return None

    start = match.start()
    # Find the closing of this function by looking for the next top-level function
    # or the end of the Script(...) block.  We use a simple heuristic: find the
    # next `function ` at the same indentation level, or `""")` which ends the Script.
    rest = source[start:]
    # Find the next `function ` that starts a new top-level JS function
    next_func = re.search(r"\n\s*function \w+\(", rest[50:])
    if next_func:
        end = start + 50 + next_func.start()
    else:
        # Fall back to end of Script block
        script_end = rest.find('"""\n')
        end = start + script_end if script_end > 0 else start + 2000

    return source[start:end]


# ============================================================================
# CORE BUG: showSaveConfirmation must call saveDeliveryCity
# ============================================================================

class TestShowSaveConfirmationCallsSaveDeliveryCity:
    """The Save button handler must persist delivery_city before saving items."""

    def test_showSaveConfirmation_calls_saveDeliveryCity(self):
        """showSaveConfirmation() must call saveDeliveryCity() to persist the
        delivery city value when the user clicks Save.

        Currently FAILS because showSaveConfirmation only calls saveAllItems()
        and does not call saveDeliveryCity().
        """
        source = _read_main_source()
        func_body = _extract_js_function(source, "showSaveConfirmation")
        assert func_body is not None, \
            "showSaveConfirmation function not found in main.py"

        assert "saveDeliveryCity" in func_body, \
            ("BUG-2: showSaveConfirmation() does not call saveDeliveryCity(). "
             "Delivery city entered by user is lost when clicking Save button.")

    def test_saveDeliveryCity_called_before_saveAllItems(self):
        """saveDeliveryCity() must be called BEFORE saveAllItems() in the
        showSaveConfirmation function so that the city is persisted first.

        Currently FAILS because saveDeliveryCity is not called at all.
        """
        source = _read_main_source()
        func_body = _extract_js_function(source, "showSaveConfirmation")
        assert func_body is not None, \
            "showSaveConfirmation function not found in main.py"

        # Both must be present
        assert "saveDeliveryCity" in func_body, \
            "BUG-2: saveDeliveryCity not called in showSaveConfirmation"

        idx_delivery = func_body.find("saveDeliveryCity")
        idx_save_all = func_body.find("saveAllItems")
        assert idx_delivery < idx_save_all, \
            ("saveDeliveryCity must be called BEFORE saveAllItems in "
             "showSaveConfirmation, but it appears after or is missing")


# ============================================================================
# DELIVERY CITY INPUT ELEMENT EXISTS
# ============================================================================

class TestDeliveryCityInputExists:
    """Verify that the delivery-city-input element is rendered on the quote page."""

    def test_delivery_city_input_element_exists_in_source(self):
        """The input with id='delivery-city-input' must be present in the quote
        detail page rendering code."""
        source = _read_main_source()

        assert 'id="delivery-city-input"' in source, \
            "delivery-city-input element not found in main.py"

    def test_delivery_city_input_has_name_attribute(self):
        """The delivery city input should have name='delivery_city' for form submission."""
        source = _read_main_source()

        # Find the area around delivery-city-input
        idx = source.find('id="delivery-city-input"')
        assert idx > 0, "delivery-city-input not found"

        # Check surrounding context (200 chars before) for name attribute
        context = source[max(0, idx - 300):idx + 100]
        assert 'name="delivery_city"' in context, \
            "delivery-city-input missing name='delivery_city' attribute"


# ============================================================================
# saveDeliveryCity FUNCTION EXISTS AND IS CORRECT
# ============================================================================

class TestSaveDeliveryCityFunction:
    """Verify that the saveDeliveryCity JS function exists and calls the right endpoint."""

    def test_saveDeliveryCity_function_exists(self):
        """saveDeliveryCity function must be defined in the JavaScript."""
        source = _read_main_source()

        assert "function saveDeliveryCity" in source, \
            "saveDeliveryCity function not defined in main.py"

    def test_saveDeliveryCity_calls_inline_patch(self):
        """saveDeliveryCity should PATCH /quotes/{id}/inline with field=delivery_city."""
        source = _read_main_source()
        func_body = _extract_js_function(source, "saveDeliveryCity")
        assert func_body is not None, \
            "saveDeliveryCity function not found"

        assert "PATCH" in func_body, \
            "saveDeliveryCity does not use PATCH method"
        assert "delivery_city" in func_body, \
            "saveDeliveryCity does not send delivery_city field"
        assert "/inline" in func_body, \
            "saveDeliveryCity does not call the /inline endpoint"

    def test_saveDeliveryCity_fires_on_save(self):
        """BUG-2 FIX: saveDeliveryCity is now called from showSaveConfirmation,
        so city is saved when the Save button is clicked (not just on blur).
        """
        source = _read_main_source()

        func_body = _extract_js_function(source, "showSaveConfirmation")
        assert func_body is not None

        assert "saveDeliveryCity" in func_body, \
            "showSaveConfirmation must call saveDeliveryCity (BUG-2 fix)"


# ============================================================================
# EDGE CASE: submitToProcurement should also call saveDeliveryCity
# ============================================================================

class TestSubmitToProcurementAlsoSavesDeliveryCity:
    """submitToProcurement() also calls saveAllItems() but not saveDeliveryCity().
    The same bug applies here -- delivery city can be lost on submit too.
    """

    def test_submitToProcurement_calls_saveDeliveryCity(self):
        """submitToProcurement() should also call saveDeliveryCity() before
        saveAllItems() to ensure delivery city is not lost on submit.

        Currently FAILS for the same reason as showSaveConfirmation.
        """
        source = _read_main_source()
        func_body = _extract_js_function(source, "submitToProcurement")
        assert func_body is not None, \
            "submitToProcurement function not found in main.py"

        assert "saveDeliveryCity" in func_body, \
            ("BUG-2 (extended): submitToProcurement() does not call "
             "saveDeliveryCity(). Delivery city can be lost when submitting "
             "to procurement.")


# ============================================================================
# INTEGRATION: delivery_city is in allowed inline update fields
# ============================================================================

class TestDeliveryCityInlineUpdateAllowed:
    """Verify that the backend inline update handler accepts delivery_city."""

    def test_delivery_city_in_allowed_fields(self):
        """delivery_city must be in the allowed_fields list for inline PATCH."""
        source = _read_main_source()

        # Find the inline update handler
        idx = source.find("async def inline_update_quote")
        if idx < 0:
            idx = source.find("def inline_update_quote")
        assert idx > 0, "inline_update_quote handler not found in main.py"

        # Get the handler body (up to 2000 chars should cover allowed_fields)
        handler_body = source[idx:idx + 2000]
        assert "'delivery_city'" in handler_body or '"delivery_city"' in handler_body, \
            "delivery_city not in allowed_fields for inline update handler"

    def test_delivery_country_in_allowed_fields(self):
        """delivery_country should also be in allowed_fields (related field)."""
        source = _read_main_source()

        idx = source.find("async def inline_update_quote")
        if idx < 0:
            idx = source.find("def inline_update_quote")
        assert idx > 0, "inline_update_quote handler not found"

        handler_body = source[idx:idx + 2000]
        assert "'delivery_country'" in handler_body or '"delivery_country"' in handler_body, \
            "delivery_country not in allowed_fields for inline update handler"


# ============================================================================
# REGRESSION: saveDeliveryCity reads value from the correct input
# ============================================================================

class TestSaveDeliveryCityReadsCorrectInput:
    """When called from showSaveConfirmation, saveDeliveryCity must read
    the current value from the delivery-city-input element.

    After the fix, the call should look like:
        var cityInput = document.getElementById('delivery-city-input');
        if (cityInput) saveDeliveryCity(cityInput.value);
    or equivalent.
    """

    def test_showSaveConfirmation_reads_delivery_city_from_input(self):
        """showSaveConfirmation should read the delivery city value from the
        DOM input element before passing it to saveDeliveryCity.

        Currently FAILS because saveDeliveryCity is not called at all.
        """
        source = _read_main_source()
        func_body = _extract_js_function(source, "showSaveConfirmation")
        assert func_body is not None

        # After the fix, the function should reference delivery-city-input
        assert "delivery-city-input" in func_body or "saveDeliveryCity" in func_body, \
            ("BUG-2: showSaveConfirmation does not read delivery_city input value. "
             "The function must get the value from delivery-city-input and pass it "
             "to saveDeliveryCity().")
