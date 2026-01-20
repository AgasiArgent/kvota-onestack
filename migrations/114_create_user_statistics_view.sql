-- Migration: 114_create_user_statistics_view
-- Description: Create view for user statistics (clients, quotes, specifications)

-- Create view for user statistics
CREATE OR REPLACE VIEW kvota.user_statistics AS
SELECT
    u.id AS user_id,
    om.organization_id,

    -- Количество клиентов (созданные пользователем + клиенты с КП от пользователя)
    COUNT(DISTINCT COALESCE(c.id, qc.id)) AS total_customers,

    -- Количество КП (созданные пользователем)
    COUNT(DISTINCT q.id) AS total_quotes,

    -- Сумма КП в USD
    COALESCE(SUM(DISTINCT q.total_usd), 0) AS total_quotes_sum_usd,
    COALESCE(SUM(DISTINCT q.total_amount), 0) AS total_quotes_sum,

    -- Количество спецификаций
    COUNT(DISTINCT s.id) AS total_specifications,

    -- Сумма спецификаций (из связанных КП)
    COALESCE(SUM(DISTINCT sq.total_usd), 0) AS total_specifications_sum_usd,
    COALESCE(SUM(DISTINCT sq.total_amount), 0) AS total_specifications_sum,

    -- Сумма профита по всем спецификациям
    COALESCE(SUM(DISTINCT sq.total_profit_usd), 0) AS total_profit_usd

FROM
    auth.users u

    -- Organization membership
    INNER JOIN kvota.organization_members om ON om.user_id = u.id
        AND om.status = 'active'

    -- Customers created by user
    LEFT JOIN kvota.customers c ON c.created_by = u.id
        AND c.organization_id = om.organization_id

    -- Quotes created by user
    LEFT JOIN kvota.quotes q ON q.created_by_user_id = u.id
        AND q.organization_id = om.organization_id
        AND q.deleted_at IS NULL

    -- Customers with quotes from user (for total_customers count)
    LEFT JOIN kvota.quotes qquotes ON qquotes.created_by_user_id = u.id
        AND qquotes.organization_id = om.organization_id
        AND qquotes.deleted_at IS NULL
    LEFT JOIN kvota.customers qc ON qc.id = qquotes.customer_id

    -- Specifications created by user
    LEFT JOIN kvota.specifications s ON s.created_by = u.id
        AND s.organization_id = om.organization_id

    -- Quotes for specifications (to get sum)
    LEFT JOIN kvota.quotes sq ON sq.id = s.quote_id
        AND sq.deleted_at IS NULL

GROUP BY
    u.id, om.organization_id;

-- Grant select on view
GRANT SELECT ON kvota.user_statistics TO authenticated;

-- Create function to get user statistics for a specific user
CREATE OR REPLACE FUNCTION kvota.get_user_statistics(target_user_id UUID, target_organization_id UUID)
RETURNS TABLE (
    user_id UUID,
    organization_id UUID,
    total_customers BIGINT,
    total_quotes BIGINT,
    total_quotes_sum_usd NUMERIC,
    total_quotes_sum NUMERIC,
    total_specifications BIGINT,
    total_specifications_sum_usd NUMERIC,
    total_specifications_sum NUMERIC,
    total_profit_usd NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        us.user_id,
        us.organization_id,
        us.total_customers,
        us.total_quotes,
        us.total_quotes_sum_usd,
        us.total_quotes_sum,
        us.total_specifications,
        us.total_specifications_sum_usd,
        us.total_specifications_sum,
        us.total_profit_usd
    FROM kvota.user_statistics us
    WHERE us.user_id = target_user_id
        AND us.organization_id = target_organization_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on function
GRANT EXECUTE ON FUNCTION kvota.get_user_statistics(UUID, UUID) TO authenticated;
