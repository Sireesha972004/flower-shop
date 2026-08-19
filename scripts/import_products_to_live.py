"""Export seller products from local SQL Server and import them to the live shop."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env")
load_dotenv(ROOT / ".env")


def fetch_local_products():
    try:
        import pyodbc
    except ImportError as exc:
        raise SystemExit("pyodbc is required for local SQL Server export.") from exc

    server = os.getenv("SQL_SERVER", r"(localdb)\Local")
    database = os.getenv("SQL_DATABASE", "FlowerShopDB")
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    connection = pyodbc.connect(conn_str)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT p.Name, p.Price, p.Category, p.Image, p.Description, u.Email
        FROM dbo.Products p
        LEFT JOIN dbo.Users u ON u.Id = p.CreatedByUserId
        WHERE p.CreatedByUserId IS NOT NULL
        ORDER BY p.CreatedAt DESC, p.Name
        """
    )
    products = []
    for row in cursor.fetchall():
        products.append(
            {
                "name": row.Name,
                "price": float(row.Price),
                "category": row.Category,
                "image": row.Image,
                "description": row.Description,
                "sellerEmail": (row.Email or "").strip().lower(),
            }
        )
    connection.close()
    return products


def login(base_url: str, email: str, password: str) -> str:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/login",
        json={"email": email, "password": password},
        timeout=30.0,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("Login succeeded but no token was returned.")
    return token


def import_products(base_url: str, token: str, products: list[dict]) -> dict:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/admin/import-products",
        headers={"Authorization": f"Bearer {token}"},
        json={"products": products},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-url",
        default=os.getenv("LIVE_URL", "https://flower-shop-npk9.onrender.com"),
        help="Live site base URL",
    )
    parser.add_argument(
        "--admin-email",
        default=os.getenv("ADMIN_EMAIL", "admin@petalandstem.local"),
        help="Admin email on the live site",
    )
    parser.add_argument(
        "--admin-password",
        default=os.getenv("ADMIN_PASSWORD", ""),
        help="Admin password on the live site",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print products that would be imported without calling the live site",
    )
    args = parser.parse_args()

    products = fetch_local_products()
    if not products:
        raise SystemExit("No seller products found in the local database.")

    print(f"Found {len(products)} seller product(s) locally.")
    if args.dry_run:
        print(json.dumps(products, indent=2))
        return

    if not args.admin_password:
        raise SystemExit("Set ADMIN_PASSWORD or pass --admin-password for live import.")

    token = login(args.live_url, args.admin_email.lower(), args.admin_password)
    result = import_products(args.live_url, token, products)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
