"""
setup_db.py
-----------
Creates `shop.db` (a SQLite database) and fills it with realistic sample
e-commerce data, so the assistant has something interesting to query.

WHY this lives in its own file:
The agent should never care *how* the data got there. By isolating database
creation here, you can rebuild a clean, known dataset at any time with:

    python setup_db.py

That makes experiments repeatable — every run starts from the exact same rows,
so when the agent gives an answer you can verify it against a fixed dataset.
"""

import sqlite3                      # built-in DB engine — no server, just one file
import random                      # to generate varied-but-plausible orders
from datetime import date, timedelta

# A FIXED seed means the "random" order data is identical on every run.
# WHY: reproducibility. If we both run this we get the same rows, so we can
# compare the agent's answers and debug against a known-good dataset.
random.seed(42)

DB_FILE = "shop.db"


# ---------------------------------------------------------------------------
# Static reference data: customers and products.
# We hand-write these so names/cities/categories read realistically instead of
# looking like gibberish. We deliberately REPEAT some cities and categories so
# that "group by city" / "by category" questions have something to group on.
# IDs are omitted here — SQLite assigns them automatically (INTEGER PRIMARY KEY).
# ---------------------------------------------------------------------------

CUSTOMERS = [
    # (name, city, signup_date)   -- signup_date is an ISO 'YYYY-MM-DD' string
    ("Alice Nguyen",   "Seattle",        "2024-01-05"),
    ("Ben Carter",     "Portland",       "2024-01-12"),
    ("Carla Diaz",     "Seattle",        "2024-01-18"),
    ("David Kim",      "San Francisco",  "2024-01-22"),
    ("Emma Wilson",    "Portland",       "2024-02-01"),
    ("Frank Moore",    "Denver",         "2024-02-03"),
    ("Grace Lee",      "Seattle",        "2024-02-10"),
    ("Henry Patel",    "Austin",         "2024-02-14"),
    ("Isla Brown",     "San Francisco",  "2024-02-20"),
    ("Jack Thompson",  "Denver",         "2024-02-25"),
    ("Kira Sato",      "Austin",         "2024-03-01"),
    ("Liam Murphy",    "Seattle",        "2024-03-05"),
    ("Mia Garcia",     "Portland",       "2024-03-11"),
    ("Noah Davis",     "San Francisco",  "2024-03-15"),
    ("Olivia Martin",  "Austin",         "2024-03-20"),
]

PRODUCTS = [
    # (name, category, price)
    ("Wireless Mouse",              "Electronics",  24.99),
    ("Mechanical Keyboard",         "Electronics",  79.99),
    ("USB-C Hub",                   "Electronics",  34.50),
    ("Noise-Cancelling Headphones", "Electronics", 199.99),
    ("27-inch Monitor",             "Electronics", 289.00),
    ("Python Crash Course",         "Books",        39.99),
    ("The Pragmatic Programmer",    "Books",        49.95),
    ("Clean Code",                  "Books",        42.00),
    ("SQL in 10 Minutes",           "Books",        29.99),
    ("Ceramic Coffee Mug",          "Home",         12.50),
    ("Stainless Water Bottle",      "Home",         19.99),
    ("Desk Lamp",                   "Home",         32.75),
    ("Throw Blanket",               "Home",         27.00),
    ("Scented Candle Set",          "Home",         22.49),
    ("Cotton T-Shirt",              "Clothing",     15.99),
    ("Hooded Sweatshirt",           "Clothing",     44.99),
    ("Running Socks (3-pack)",      "Clothing",     13.99),
    ("Building Blocks Set",         "Toys",         34.99),
    ("Puzzle 1000pc",               "Toys",         18.99),
    ("Remote Control Car",          "Toys",         54.99),
]


def main():
    # Connecting to a non-existent file CREATES it. shop.db appears in the
    # current directory the first time we write to it.
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Drop tables first so this script is SAFELY RE-RUNNABLE. Without this,
    # running twice would stack duplicate rows on top of the old ones.
    # Order matters: drop children (order_items, orders) before parents.
    cur.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
        """
    )

    # Create the schema. The FOREIGN KEY lines aren't strictly enforced by
    # default in SQLite, but we include them because they DOCUMENT how the
    # tables relate — and later the LLM reads this exact schema to figure out
    # which columns to JOIN on.
    cur.executescript(
        """
        CREATE TABLE customers (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            city        TEXT NOT NULL,
            signup_date TEXT NOT NULL          -- ISO date 'YYYY-MM-DD'
        );

        CREATE TABLE products (
            id       INTEGER PRIMARY KEY,
            name     TEXT NOT NULL,
            category TEXT NOT NULL,
            price    REAL NOT NULL
        );

        CREATE TABLE orders (
            id           INTEGER PRIMARY KEY,
            customer_id  INTEGER NOT NULL,
            order_date   TEXT NOT NULL,        -- ISO date 'YYYY-MM-DD'
            total_amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE order_items (
            id         INTEGER PRIMARY KEY,
            order_id   INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity   INTEGER NOT NULL,
            FOREIGN KEY (order_id)   REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        """
    )

    # executemany runs the same INSERT once per tuple in the list — a compact
    # way to bulk-load our hand-written reference rows.
    cur.executemany(
        "INSERT INTO customers (name, city, signup_date) VALUES (?, ?, ?)",
        CUSTOMERS,
    )
    cur.executemany(
        "INSERT INTO products (name, category, price) VALUES (?, ?, ?)",
        PRODUCTS,
    )

    # Read back the IDs SQLite actually assigned. We DON'T assume "id = index+1"
    # — we ask the DB — so the code stays correct even if the data changes.
    customer_ids = [row[0] for row in cur.execute("SELECT id FROM customers")]
    products = cur.execute("SELECT id, price FROM products").fetchall()

    # -----------------------------------------------------------------------
    # Generate ~50 orders spread across ~4 months so that date-range and
    # aggregation questions ("orders per month", "revenue in April") work.
    # -----------------------------------------------------------------------
    start = date(2024, 3, 1)
    span_days = 120  # roughly March through June

    for _ in range(50):
        customer_id = random.choice(customer_ids)
        order_day = start + timedelta(days=random.randint(0, span_days))
        order_date = order_day.isoformat()

        # Insert the order with a placeholder total of 0. We UPDATE it below
        # once we know its line items. WHY: total_amount should equal the sum
        # of its order_items, so "order total" questions and "sum of items"
        # questions give the same answer — the data stays internally consistent.
        cur.execute(
            "INSERT INTO orders (customer_id, order_date, total_amount) VALUES (?, ?, 0)",
            (customer_id, order_date),
        )
        order_id = cur.lastrowid  # the id just assigned to this new order

        # Each order gets 1–4 DISTINCT products (random.sample avoids repeats).
        chosen = random.sample(products, k=random.randint(1, 4))
        total = 0.0
        for product_id, price in chosen:
            qty = random.randint(1, 3)
            total += price * qty
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)",
                (order_id, product_id, qty),
            )

        # Now write the real total (rounded to cents) back onto the order.
        cur.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (round(total, 2), order_id),
        )

    # commit() flushes everything above to disk. Nothing is permanent until now.
    conn.commit()

    # Sanity report so you can SEE it worked without opening a DB browser.
    print(f"Created {DB_FILE} with:")
    for table in ("customers", "products", "orders", "order_items"):
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:12} {count:>3} rows")

    conn.close()


if __name__ == "__main__":
    main()