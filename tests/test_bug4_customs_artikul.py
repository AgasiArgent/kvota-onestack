"""
BUG-4: Customs HS Code Validation (workflow_service side)

HS code (ТН ВЭД) must be mandatory before customs completion. The service-layer
validation in workflow_service.complete_customs() is the single source of truth
that remains after Phase 6C-2B-Mega-A archived the FastHTML /customs/{quote_id}
page (legacy-fasthtml/ops_deal_finance_customs_logistics.py).

Previously this file also contained tests for:
- customs Handsontable colHeaders / columns config (TestColHeadersIncludeArtikul,
  TestColumnsConfigIncludeProductCode, TestProductCodeDataFlow)
- _build_customs_item row-dict shape (TestBuildCustomsItemIncludesProductCode,
  TestProductCodeEdgeCases)
- saveCustomsItems JS payload (TestSaveDoesNotSendProductCode)
- /customs/{quote_id} POST hs_code validation block (TestHsCodeValidationOnCompletion)

Those classes were removed in Phase 6C-2B-Mega-A because they target code that
now lives in legacy-fasthtml/ and no longer runs. The hs_code validation in
workflow_service.complete_customs() is the authoritative check; the UI will be
rebuilt via Next.js + /api/customs post-cutover.
"""

import pytest
import re
import os


# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
WORKFLOW_SERVICE_PY = os.path.join(_PROJECT_ROOT, "services", "workflow_service.py")


def _read_source(path):
    """Read source file without importing (avoids sentry_sdk and other deps)."""
    with open(path) as f:
        return f.read()


# ==============================================================================
# HS code validation in complete_customs (workflow_service.py)
# ==============================================================================

class TestHsCodeValidationInWorkflowService:
    """The complete_customs function in workflow_service.py must validate
    hs_code for all items before completing customs."""

    def _get_complete_customs_source(self):
        """Extract complete_customs function source from workflow_service.py."""
        source = _read_source(WORKFLOW_SERVICE_PY)
        match = re.search(
            r'(def complete_customs\(.*?\n(?:    .*\n)*)',
            source,
        )
        assert match, "complete_customs function not found in workflow_service.py"
        return match.group(1)

    def test_complete_customs_checks_hs_codes(self):
        """complete_customs should validate that all items have hs_code."""
        fn_source = self._get_complete_customs_source()
        has_hs_validation = "hs_code" in fn_source
        assert has_hs_validation, (
            "complete_customs() in workflow_service.py does NOT validate hs_code. "
            "Items with empty hs_code should prevent customs completion."
        )

    def test_complete_customs_queries_items(self):
        """complete_customs should query quote_items to check hs_code."""
        fn_source = self._get_complete_customs_source()
        has_items_query = "quote_items" in fn_source
        assert has_items_query, (
            "complete_customs() does not query quote_items. "
            "It should fetch items and verify all have hs_code before completing."
        )

    def test_complete_customs_returns_error_for_missing_hs(self):
        """complete_customs should return error when hs_code is missing."""
        fn_source = self._get_complete_customs_source()
        has_hs_error = (
            "hs_code" in fn_source
            and "error" in fn_source.lower()
        )
        assert has_hs_error, (
            "complete_customs() must return an error when items lack hs_code. "
            "Currently it completes regardless of hs_code presence."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
