"""Drift detector: rate_resolver.FROZEN_STATUSES must mirror the
post-APPROVED set of WorkflowStatus values. We keep them as strings
inside rate_resolver to avoid a circular import; this test catches
any drift if a future migration adds/renames a workflow status."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.rate_resolver import FROZEN_STATUSES
from services.workflow_service import WorkflowStatus


def test_frozen_statuses_mirror_workflow_enum():
    expected = {
        WorkflowStatus.APPROVED.value,
        WorkflowStatus.SENT_TO_CLIENT.value,
        WorkflowStatus.CLIENT_NEGOTIATION.value,
        WorkflowStatus.PENDING_SPEC_CONTROL.value,
        WorkflowStatus.PENDING_SIGNATURE.value,
        WorkflowStatus.DEAL.value,
        WorkflowStatus.REJECTED.value,
        WorkflowStatus.CANCELLED.value,
    }
    assert FROZEN_STATUSES == expected, (
        f"FROZEN_STATUSES drift detected. Expected {expected} but got "
        f"{FROZEN_STATUSES}. If you renamed a WorkflowStatus value, "
        "update services/rate_resolver.py:FROZEN_STATUSES too."
    )
