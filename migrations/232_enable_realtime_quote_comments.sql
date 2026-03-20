-- Migration 232: Enable Supabase Realtime on quote_comments
-- Required for the real-time chat panel on the quote detail page.
-- Note: Caddy/Kong may also need WebSocket passthrough config on VPS.

ALTER PUBLICATION supabase_realtime ADD TABLE kvota.quote_comments;
