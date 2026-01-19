#!/usr/bin/env python3
"""Check database schema for bug testing"""
import os
import sys
from sqlalchemy import create_engine, inspect, MetaData, Table, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment")
    sys.exit(1)

print(f"Connecting to database...")

try:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    print("\n" + "="*80)
    print("DATABASE SCHEMA INSPECTION")
    print("="*80)

    # Get all tables
    tables = inspector.get_table_names()
    print(f"\nFound {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  - {table}")

    # Check for product/item related tables
    print("\n" + "="*80)
    print("PRODUCT/ITEM RELATED TABLES")
    print("="*80)

    product_tables = [t for t in tables if 'product' in t.lower() or 'item' in t.lower() or 'quotation' in t.lower()]

    for table_name in product_tables:
        print(f"\n\nTable: {table_name}")
        print("-" * 40)
        columns = inspector.get_columns(table_name)
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            col_type = str(col['type'])
            print(f"  {col['name']:30s} {col_type:20s} {nullable}")

    # Check customers table
    print("\n" + "="*80)
    print("CUSTOMERS TABLE")
    print("="*80)

    if 'customers' in tables:
        print(f"\n\nTable: customers")
        print("-" * 40)
        columns = inspector.get_columns('customers')
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            col_type = str(col['type'])
            print(f"  {col['name']:30s} {col_type:20s} {nullable}")

        # Check indexes
        print("\nIndexes:")
        indexes = inspector.get_indexes('customers')
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['column_names']} (unique={idx['unique']})")

    # Check contacts table
    print("\n" + "="*80)
    print("CONTACTS TABLE")
    print("="*80)

    if 'contacts' in tables:
        print(f"\n\nTable: contacts")
        print("-" * 40)
        columns = inspector.get_columns('contacts')
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            col_type = str(col['type'])
            print(f"  {col['name']:30s} {col_type:20s} {nullable}")

    # Check specifications table
    print("\n" + "="*80)
    print("SPECIFICATIONS TABLE")
    print("="*80)

    spec_tables = [t for t in tables if 'spec' in t.lower()]
    for table_name in spec_tables:
        print(f"\n\nTable: {table_name}")
        print("-" * 40)
        columns = inspector.get_columns(table_name)
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            col_type = str(col['type'])
            print(f"  {col['name']:30s} {col_type:20s} {nullable}")

    print("\n" + "="*80)
    print("INSPECTION COMPLETE")
    print("="*80)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
