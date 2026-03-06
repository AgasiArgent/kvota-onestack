-- Add manager_id column to customers table
ALTER TABLE kvota.customers ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES auth.users(id);

-- Populate manager_id from created_by for existing customers
UPDATE kvota.customers SET manager_id = created_by WHERE created_by IS NOT NULL;

-- Create index for filtering
CREATE INDEX IF NOT EXISTS idx_customers_manager_id ON kvota.customers(manager_id);
