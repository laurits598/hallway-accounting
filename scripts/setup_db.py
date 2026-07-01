#!/usr/bin/env python3
"""
Setup SQLite database for Kollegianeren with seed data from JSON files.
"""

import sqlite3
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "kollegianeren.db"
SEED_DIR = PROJECT_ROOT / "data" / "seed"

def setup_database():
    """Create database schema and seed with data from JSON files."""

    # Connect (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()

    # Drop existing tables if they exist (preserve purchases)
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS residents")

    # Create tables
    cursor.execute("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        retail_price REAL,
        price REAL NOT NULL,
        image TEXT,
        active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE residents (
        rid INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        room TEXT NOT NULL,
        image TEXT,
        active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create purchases table only if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        resident_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        price REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (resident_id) REFERENCES residents(rid)
    )
    """)

    # One daily Foodclub event.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS foodclub_events (
        fid INTEGER PRIMARY KEY,
        event_date DATE NOT NULL UNIQUE,
        chef_rid INTEGER,
        dish TEXT,
        price_per_person REAL,
        total_price REAL,
        notes TEXT,
        FOREIGN KEY (chef_rid) REFERENCES residents(rid)
    )
    """)

    # Residents who attended a daily Foodclub event.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS foodclub_attended (
        fid INTEGER NOT NULL,
        rid INTEGER NOT NULL,
        attendance_value TEXT NOT NULL DEFAULT '1',
        PRIMARY KEY (fid, rid),
        FOREIGN KEY (fid) REFERENCES foodclub_events(fid),
        FOREIGN KEY (rid) REFERENCES residents(rid)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluebook_months (
        id INTEGER PRIMARY KEY,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        sheet_name TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (year, month)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluebook_expenses (
        xid INTEGER PRIMARY KEY,
        bmid INTEGER NOT NULL,
        rid INTEGER,
        expense_date DATE,
        description TEXT,
        amount REAL NOT NULL,
        source_row INTEGER,
        source_slot INTEGER,
        FOREIGN KEY (bmid) REFERENCES bluebook_months(id) ON DELETE CASCADE,
        FOREIGN KEY (rid) REFERENCES residents(rid),
        UNIQUE (bmid, source_row, source_slot)
    )
    """)

    # Seed products
    with open(SEED_DIR / "products.json", "r") as f:
        products = json.load(f)

    for product in products:
        retail_price = product.get("retail_price")
        retail_price = float(retail_price) if retail_price and retail_price != "" else None

        cursor.execute("""
        INSERT INTO products (name, retail_price, price, image)
        VALUES (?, ?, ?, ?)
        """, (
            product["name"],
            retail_price,
            float(product["price"]),
            product.get("image") or None
        ))

    # Seed residents
    with open(SEED_DIR / "residents.json", "r") as f:
        residents = json.load(f)

    for resident in residents:
        cursor.execute("""
        INSERT INTO residents (name, room, image)
        VALUES (?, ?, ?)
        """, (
            resident["name"],
            resident["room"],
            resident.get("image") or None
        ))

    conn.commit()
    conn.close()

    print("Created %s" % DB_PATH)
    print("Seeded %d products" % len(products))
    print("Seeded %d residents" % len(residents))

if __name__ == "__main__":
    setup_database()
