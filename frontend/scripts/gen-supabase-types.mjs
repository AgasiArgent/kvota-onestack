import pg from 'pg';
const { Client } = pg;

const client = new Client({
  connectionString: process.argv[2],
});
await client.connect();

const schema = 'kvota';

// Get all tables
const { rows: tables } = await client.query(`
  SELECT table_name FROM information_schema.tables
  WHERE table_schema = $1 AND table_type = 'BASE TABLE'
  ORDER BY table_name
`, [schema]);

// Get all views — emitted as read-only types (Row only, no Insert/Update).
const { rows: views } = await client.query(`
  SELECT table_name FROM information_schema.views
  WHERE table_schema = $1
  ORDER BY table_name
`, [schema]);

// Get columns for each table AND view (information_schema.columns covers both)
const { rows: columns } = await client.query(`
  SELECT table_name, column_name, data_type, udt_name, is_nullable,
         column_default, character_maximum_length
  FROM information_schema.columns
  WHERE table_schema = $1
  ORDER BY table_name, ordinal_position
`, [schema]);

// Get enums
const { rows: enums } = await client.query(`
  SELECT t.typname, e.enumlabel
  FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
  JOIN pg_namespace n ON t.typnamespace = n.oid
  WHERE n.nspname = $1
  ORDER BY t.typname, e.enumsortorder
`, [schema]);

// Map PG types to TS
function pgToTs(dataType, udtName, isNullable) {
  const map = {
    'uuid': 'string',
    'text': 'string',
    'character varying': 'string',
    'varchar': 'string',
    'integer': 'number',
    'smallint': 'number',
    'bigint': 'number',
    'numeric': 'number',
    'real': 'number',
    'double precision': 'number',
    'boolean': 'boolean',
    'jsonb': 'Json',
    'json': 'Json',
    'timestamp with time zone': 'string',
    'timestamp without time zone': 'string',
    'date': 'string',
    'time with time zone': 'string',
    'time without time zone': 'string',
    'ARRAY': 'Json',
    'USER-DEFINED': 'string',
    'bytea': 'string',
    'inet': 'string',
    'interval': 'string',
  };
  return map[dataType] || 'string';
}

// Group columns by table
const tableColumns = {};
for (const col of columns) {
  if (!tableColumns[col.table_name]) tableColumns[col.table_name] = [];
  tableColumns[col.table_name].push(col);
}

// Generate output
let out = `export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  kvota: {
    Tables: {\n`;

for (const { table_name } of tables) {
  const cols = tableColumns[table_name] || [];
  
  // Row type
  out += `      ${table_name}: {\n        Row: {\n`;
  for (const col of cols) {
    const tsType = pgToTs(col.data_type, col.udt_name, col.is_nullable);
    const nullable = col.is_nullable === 'YES' ? ' | null' : '';
    out += `          ${col.column_name}: ${tsType}${nullable}\n`;
  }
  out += `        }\n`;
  
  // Insert type
  out += `        Insert: {\n`;
  for (const col of cols) {
    const tsType = pgToTs(col.data_type, col.udt_name, col.is_nullable);
    const nullable = col.is_nullable === 'YES' ? ' | null' : '';
    const optional = (col.column_default !== null || col.is_nullable === 'YES') ? '?' : '';
    out += `          ${col.column_name}${optional}: ${tsType}${nullable}\n`;
  }
  out += `        }\n`;
  
  // Update type
  out += `        Update: {\n`;
  for (const col of cols) {
    const tsType = pgToTs(col.data_type, col.udt_name, col.is_nullable);
    const nullable = col.is_nullable === 'YES' ? ' | null' : '';
    out += `          ${col.column_name}?: ${tsType}${nullable}\n`;
  }
  out += `        }\n`;
  
  out += `        Relationships: []\n      }\n`;
}

out += `    }
    Views: {
`;

for (const { table_name } of views) {
  const cols = tableColumns[table_name] || [];
  // Views are read-only: Row only. Columns often nullable due to outer joins
  // or expressions — trust information_schema.is_nullable.
  out += `      ${table_name}: {\n        Row: {\n`;
  for (const col of cols) {
    const tsType = pgToTs(col.data_type, col.udt_name, col.is_nullable);
    const nullable = col.is_nullable === 'YES' ? ' | null' : '';
    out += `          ${col.column_name}: ${tsType}${nullable}\n`;
  }
  out += `        }\n        Relationships: []\n      }\n`;
}

out += `    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
  }
}\n`;

console.log(out);

await client.end();
