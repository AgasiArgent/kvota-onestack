"""
Thin JSON API layer for Next.js frontend.
Mounted at /api/* in main.py.

Endpoints here are called by the Next.js app for operations
that require server-side Python (calculation, workflow, exports).
Simple CRUD goes directly through Supabase client in Next.js.
"""
