"""Notes /api/notes/* endpoints.

Thin wrapper over api.notes handlers. Mounted with prefix="/notes".
See api/notes.py for business logic + docstrings.
"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.notes import (
    create_note as _create_note,
    delete_note as _delete_note,
    list_notes as _list_notes,
    update_note as _update_note,
)

router = APIRouter(tags=["notes"])


@router.get("")
async def get_notes(request: Request) -> JSONResponse:
    """List notes for an entity (visible_to enforced by DB RLS)."""
    return await _list_notes(request)


@router.post("")
async def post_note(request: Request) -> JSONResponse:
    """Create a new note with author_id + frozen author_role."""
    return await _create_note(request)


@router.patch("/{note_id}")
async def patch_note(request: Request, note_id: str) -> JSONResponse:
    """Update a note (author or admin only)."""
    return await _update_note(request, note_id)


@router.delete("/{note_id}")
async def delete_note_endpoint(request: Request, note_id: str) -> JSONResponse:
    """Delete a note (author or admin only)."""
    return await _delete_note(request, note_id)
