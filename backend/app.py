import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*paths, **kwargs):
        for path in paths:
            if not path:
                continue
            p = Path(path)
            if not p.exists():
                continue
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key.strip(), value)

import httpx
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

try:
    import pyodbc
except ImportError:
    pyodbc = None
import sqlite3


ROOT = Path(__file__).resolve().parent
# Load environment from the backend folder and project root.
load_dotenv(str(ROOT / ".env"), override=True)
load_dotenv(str(ROOT.parent / ".env"), override=True)

FRONTEND_DIR = ROOT.parent / "frontend"
UPLOADS_DIR = FRONTEND_DIR / "uploads"
SQL_SERVER = os.getenv("SQL_SERVER", r"(localdb)\Local")
SQL_DATABASE = os.getenv("SQL_DATABASE", "FlowerShopDB")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
PORT = int(os.getenv("PORT", "3001"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@petalandstem.local").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
AI_PROVIDER = "gemini"
AI_MODEL = os.getenv("AI_MODEL", "gemini-flash-latest").strip()
AI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "AI_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-2.0-flash-lite"
    ).split(",")
    if model.strip()
]
AI_API_KEY = os.getenv("AI_API_KEY", "").strip() or GEMINI_API_KEY
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(ROOT / "flowershop.db")))


def using_sqlite():
    if os.getenv("RENDER"):
        return True
    if os.getenv("USE_SQLITE", "").strip().lower() in {"1", "true", "yes"}:
        return True
    return pyodbc is None
MAX_DELIVERY_ADDRESS_LENGTH = 1000
CURRENCY_SYMBOL = "₹"
AI_SYSTEM_PROMPT = (
    "You are a friendly flower shop assistant for Petal & Stem. "
    "All prices use the rupee symbol (₹). Use the available tools when customers ask "
    "about products, their cart, delivery, orders, gifts, coupons, or addresses. "
    "If the user needs store data, retrieve it from the tools instead of guessing. "
    "Always answer clearly and politely."
)
AI_TOOL_DEFINITIONS = [
    {
        "name": "search_flowers",
        "description": "Search bouquets and gift items by occasion, budget, or keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "occasion": {"type": "string", "description": "The occasion for the flowers."},
                "budget": {"type": "number", "description": "Maximum budget in ₹."},
                "keywords": {"type": "string", "description": "Search keywords."},
                "count": {"type": "integer", "description": "Number of results to return."}
            },
            "required": ["count"]
        }
    },
    {
        "name": "get_flower_details",
        "description": "Look up detailed information for a specific product.",
        "parameters": {
            "type": "object",
            "properties": {
                "productId": {"type": "string", "description": "The identifier of the product to retrieve."}
            },
            "required": ["productId"]
        }
    },
    {
        "name": "recommend_flowers",
        "description": "Recommend bouquets based on occasion and budget.",
        "parameters": {
            "type": "object",
            "properties": {
                "occasion": {"type": "string", "description": "The occasion for the recommendations."},
                "budget": {"type": "number", "description": "Maximum budget in ₹."}
            }
        }
    },
    {
        "name": "search_gift_items",
        "description": "Return gift items available in the shop.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "view_cart",
        "description": "Show the customer's current shopping cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "customerId": {"type": "string", "description": "The logged-in user id."}
            },
            "required": ["customerId"]
        }
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the customer's shopping cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "productId": {"type": "string", "description": "The product id to add."},
                "quantity": {"type": "integer", "description": "Number of units to add."}
            },
            "required": ["productId"]
        }
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a product from the customer's cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "productId": {"type": "string", "description": "The product id to remove."}
            },
            "required": ["productId"]
        }
    },
    {
        "name": "update_quantity",
        "description": "Update the quantity of a product already in the cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "productId": {"type": "string", "description": "The product id to update."},
                "quantity": {"type": "integer", "description": "The new quantity."}
            },
            "required": ["productId", "quantity"]
        }
    },
    {
        "name": "apply_coupon",
        "description": "Apply a coupon code and return the updated total.",
        "parameters": {
            "type": "object",
            "properties": {
                "couponCode": {"type": "string", "description": "The coupon code to apply."}
            },
            "required": ["couponCode"]
        }
    },
    {
        "name": "estimate_delivery",
        "description": "Estimate whether a delivery date is available.",
        "parameters": {
            "type": "object",
            "properties": {
                "requestedDate": {"type": "string", "description": "The desired delivery date in ISO format."}
            },
            "required": ["requestedDate"]
        }
    },
    {
        "name": "get_delivery_slots",
        "description": "List available delivery time slots for the upcoming week.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "create_order",
        "description": "Create a new order from the current cart.",
        "parameters": {
            "type": "object",
            "properties": {
                "deliveryAddress": {"type": "string", "description": "Delivery address for the order."},
                "deliveryDate": {"type": "string", "description": "Optional delivery date in ISO format."},
                "paymentMethod": {"type": "string", "description": "Payment method used for the order."}
            },
            "required": ["deliveryAddress"]
        }
    },
    {
        "name": "track_order",
        "description": "Get status and details for an existing order.",
        "parameters": {
            "type": "object",
            "properties": {
                "orderId": {"type": "string", "description": "The order id to track."}
            },
            "required": ["orderId"]
        }
    },
    {
        "name": "get_order_history",
        "description": "Return the customer's past orders.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "cancel_order",
        "description": "Cancel an existing order.",
        "parameters": {
            "type": "object",
            "properties": {
                "orderId": {"type": "string", "description": "The order to cancel."}
            },
            "required": ["orderId"]
        }
    },
    {
        "name": "suggest_greeting_card",
        "description": "Suggest message ideas for a greeting card.",
        "parameters": {
            "type": "object",
            "properties": {
                "occasion": {"type": "string", "description": "The occasion to write about."}
            },
            "required": []
        }
    },
    {
        "name": "check_inventory",
        "description": "Check the inventory quantity for a product.",
        "parameters": {
            "type": "object",
            "properties": {
                "productId": {"type": "string", "description": "The product id to check stock for."}
            },
            "required": ["productId"]
        }
    },
    {
        "name": "get_customer_addresses",
        "description": "Return saved delivery addresses for the customer.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "save_new_address",
        "description": "Save a new delivery address for the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {"type": "object", "description": "Address fields to save.", "properties": {
                    "label": {"type": "string"},
                    "recipient": {"type": "string"},
                    "line1": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "postalCode": {"type": "string"},
                    "country": {"type": "string"},
                    "phone": {"type": "string"}
                }}
            },
            "required": ["address"]
        }
    }
]
USER_REQUIRED_TOOLS = {
    "add_to_cart",
    "remove_from_cart",
    "update_quantity",
    "view_cart",
    "apply_coupon",
    "estimate_delivery",
    "get_delivery_slots",
    "create_order",
    "track_order",
    "get_order_history",
    "cancel_order",
    "check_inventory",
    "get_customer_addresses",
    "save_new_address",
}

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

ORDER_STATUSES = {
    "pending": "Order received",
    "confirmed": "Confirmed",
    "preparing": "Preparing bouquet",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "refunded": "Refunded",
}
DISPLAY_ORDER_STATUS_LABELS = {
    "pending": "Pending",
    "confirmed": "Confirmed",
    "preparing": "Packed",
    "out_for_delivery": "Shipped",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "refunded": "Refunded",
}
PAYMENT_STATUSES = {
    "pending": "Pending",
    "paid": "Paid",
    "failed": "Failed",
    "refunded": "Refunded",
}
PAYMENT_METHODS = {
    "online": "Online payment",
    "cash": "Cash in hand",
}
ORDER_STATUS_FLOW = [
    "pending",
    "confirmed",
    "preparing",
    "out_for_delivery",
    "delivered",
]
ORDER_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"out_for_delivery", "cancelled"},
    "out_for_delivery": {"delivered", "cancelled"},
    "delivered": {"refunded"},
    "cancelled": set(),
    "refunded": set(),
}
CANCELLABLE_STATUSES = {"pending", "confirmed", "preparing"}
TERMINAL_STATUSES = {"delivered", "cancelled", "refunded"}
SELLER_NEXT_STATUS = {
    "confirmed": "preparing",
    "preparing": "out_for_delivery",
    "out_for_delivery": "delivered",
}
SELLER_ADVANCE_ACTIONS = {
    "preparing": "Preparing bouquet",
    "out_for_delivery": "Out for delivery",
    "delivered": "Mark delivered",
}
ACTOR_ROLE_LABELS = {
    "buyer": "Buyer said",
    "seller": "Seller said",
    "admin": "Store said",
    "system": "System update",
}
EVENT_TYPES = {"status", "note", "payment"}
STATUS_EVENT_NOTES = {
    "pending": "Order placed. Waiting for the seller to confirm.",
    "confirmed": "Seller confirmed the order.",
    "preparing": "Seller started preparing the bouquet.",
    "out_for_delivery": "Seller handed the order to delivery.",
    "delivered": "Seller marked the order as delivered.",
    "cancelled": "This order was cancelled.",
    "refunded": "This order was refunded.",
}
STATUS_EVENT_LOCATIONS = {
    "pending": "Order received",
    "confirmed": "Seller workshop",
    "preparing": "Florist studio",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "refunded": "Refunded",
}

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

ORDER_SELECT_SQL = """
    SELECT o.Id, o.UserId, o.Total, o.DeliveryAddress, o.DeliveryDate,
           o.PaymentMethod, o.PaymentStatus, o.Status, o.TrackingNumber, o.CreatedAt,
           o.UpdatedAt, o.DeliveredAt, o.CancelledAt, u.Email, u.Name
    FROM dbo.Orders o
    JOIN dbo.Users u ON u.Id = o.UserId
"""


@app.after_request
def add_security_headers(response):
    origin = request.headers.get("Origin")
    if ALLOWED_ORIGINS:
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    )
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def api_options(path):
    return jsonify({}), 200

PRODUCTS = [
    ("p1", "Blush Romance Bouquet", 45.00, "Roses",
     "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=600",
     "A soft blush arrangement of garden roses, ranunculus, and eucalyptus."),
    ("p2", "Sunlit Meadow", 38.50, "Mixed",
     "https://images.unsplash.com/photo-1487070183336-b863922373d4?w=600",
     "Sunflowers, daisies, and wild greens for a bright, cheerful bunch."),
    ("p3", "Velvet Plum", 52.00, "Premium",
     "https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=600",
     "Deep plum dahlias and burgundy roses with trailing amaranthus."),
    ("p4", "Pure White Peony", 60.00, "Premium",
     "https://images.unsplash.com/photo-1509587584298-0f3b3a3a1797?w=600",
     "Elegant white peonies and lisianthus, wrapped in natural kraft."),
   
]


def sync_catalog_prices(connection):
    marker = connection.execute(
        "SELECT Price FROM dbo.Products WHERE Id = 'p1'"
    ).fetchone()
    if marker and float(marker.Price) > 500:
        connection.execute("UPDATE dbo.Products SET Price = ROUND(Price / 83.0, 2)")
        connection.execute(
            """
            UPDATE dbo.OrderItems
            SET Price = ROUND(Price / 83.0, 2)
            WHERE Price >= 50
            """
        )
        connection.execute(
            """
            UPDATE dbo.Orders
            SET Total = ROUND(Total / 83.0, 2)
            WHERE Total >= 50
            """
        )
    for product in PRODUCTS:
        connection.execute(
            "UPDATE dbo.Products SET Price = ? WHERE Id = ?",
            product[2], product[0],
        )


def sync_catalog_images(connection):
    for product in PRODUCTS:
        connection.execute(
            "UPDATE dbo.Products SET Image = ? WHERE Id = ?",
            product[4],
            product[0],
        )


def connection_string(database):
    return (
        f"DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={database};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )


def adapt_sqlite_sql(sql):
    adapted = str(sql).replace("dbo.", "")
    adapted = adapted.replace("LEN(", "LENGTH(")
    adapted = adapted.replace("SYSUTCDATETIME()", "datetime('now')")
    if re.search(r"SELECT\s+TOP\s+1\s", adapted, re.I):
        adapted = re.sub(r"SELECT\s+TOP\s+1\s", "SELECT ", adapted, count=1, flags=re.I)
        adapted = adapted.rstrip().rstrip(";") + " LIMIT 1"
    return adapted


class AttrRow:
    def __init__(self, row):
        self._mapping = dict(row)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._mapping[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, key):
        return self._mapping[key]


class SqliteConnection:
    def __init__(self, path):
        self._conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, *params):
        cursor = self._conn.execute(adapt_sqlite_sql(sql), params if params else ())
        return SqliteCursor(cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        return False


class SqliteCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        row = self._cursor.fetchone()
        return AttrRow(row) if row is not None else None

    def fetchall(self):
        return [AttrRow(row) for row in self._cursor.fetchall()]


def sanitize_for_gemini(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): sanitize_for_gemini(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_gemini(item) for item in value]
    return str(value)


def gemini_tool_declarations():
    return [{
        "functionDeclarations": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for tool in AI_TOOL_DEFINITIONS
        ]
    }]


def normalize_tool_name(name):
    aliases = {
        "list_products": "search_flowers",
        "get_products": "search_flowers",
        "list_flowers": "search_flowers",
        "recommend_bouquets": "recommend_flowers",
        "get_product_details": "get_flower_details",
        "get_flower_detail": "get_flower_details",
    }
    return aliases.get(str(name or "").strip(), str(name or "").strip())


def parse_gemini_candidate(candidate):
    parts = candidate.get("content", {}).get("parts", [])
    text_parts = []
    model_parts = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("text"):
            text_parts.append(part["text"])
        if part.get("functionCall"):
            model_parts.append(part)
    return "".join(text_parts).strip(), model_parts


def extract_gemini_error(data):
    if not isinstance(data, dict):
        return None
    prompt_feedback = data.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")
    if block_reason:
        return f"Request blocked by safety filters ({block_reason})."
    candidates = data.get("candidates") or []
    if candidates:
        finish_reason = candidates[0].get("finishReason")
        if finish_reason and finish_reason not in {"STOP", "MAX_TOKENS"}:
            return f"Model stopped generating a reply ({finish_reason})."
    return None


def gemini_agent_chat(messages, tool_runner):
    if not AI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is required for AI chat.")

    system_instruction = None
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = str(msg.get("content", "") or "").strip()
        if not content:
            continue
        if role == "system":
            system_instruction = {"parts": [{"text": content}]}
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})

    if not contents:
        raise RuntimeError("At least one user message is required.")

    headers = {
        "x-goog-api-key": AI_API_KEY,
        "Content-Type": "application/json",
    }
    tools = gemini_tool_declarations()
    models_to_try = [AI_MODEL]
    for model in AI_FALLBACK_MODELS:
        if model not in models_to_try:
            models_to_try.append(model)

    last_error = None
    for model in models_to_try:
        working_contents = [dict(item) for item in contents]
        for _ in range(6):
            payload = {
                "contents": working_contents,
                "tools": tools,
                "generationConfig": {"temperature": 0.7},
            }
            if system_instruction:
                payload["systemInstruction"] = system_instruction

            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            response = httpx.post(url, json=payload, headers=headers, timeout=45.0)
            if response.status_code == 429:
                if model != models_to_try[-1]:
                    last_error = response
                    break
                retry_delay = 2
                try:
                    details = response.json().get("error", {}).get("details", [])
                    for detail in details:
                        if detail.get("@type", "").endswith("RetryInfo"):
                            retry_delay = max(2, int(float(detail.get("retryDelay", "2s").rstrip("s") or 2)))
                except Exception:
                    pass
                time.sleep(retry_delay)
                response = httpx.post(url, json=payload, headers=headers, timeout=45.0)
            if response.status_code in {404, 503} and model != models_to_try[-1]:
                last_error = response
                break
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as ex:
                if ex.response.status_code == 429:
                    detail = ex.response.json().get("error", {}).get("message", str(ex))
                    raise RuntimeError(
                        "Gemini quota exceeded for all configured models. "
                        "Wait a minute and try again, or update AI_MODEL in backend/.env. "
                        f"Details: {detail}"
                    ) from ex
                if ex.response.status_code == 400:
                    detail = ex.response.text[:500]
                    app.logger.error("Gemini 400 response: %s", detail)
                raise

            data = response.json()
            generation_error = extract_gemini_error(data)
            candidates = data.get("candidates") or []
            if not candidates:
                if generation_error:
                    return {"content": generation_error, "model": model}
                continue

            text, model_parts = parse_gemini_candidate(candidates[0])
            if model_parts:
                working_contents.append({"role": "model", "parts": model_parts})
                response_parts = []
                for part in model_parts:
                    call = part.get("functionCall") or {}
                    raw_name = call.get("name", "")
                    normalized_name = normalize_tool_name(raw_name)
                    args = call.get("args") or {}
                    if not isinstance(args, dict):
                        args = {}
                    result = sanitize_for_gemini(tool_runner(normalized_name, args))
                    response_parts.append({
                        "functionResponse": {
                            "name": raw_name,
                            "response": result,
                        }
                    })
                working_contents.append({"role": "user", "parts": response_parts})
                continue

            if text:
                return {"content": text, "model": model}
            if generation_error:
                return {"content": generation_error, "model": model}

        if last_error is not None and model != models_to_try[-1]:
            continue

    if last_error is not None:
        last_error.raise_for_status()
    return {
        "content": (
            "I couldn't prepare a reply just now. Please try asking again, "
            "for example: 'Recommend birthday flowers under ₹50.'"
        ),
        "model": AI_MODEL,
    }


def gemini_chat_completion(messages):
    return gemini_agent_chat(messages, lambda *_args, **_kwargs: {
        "error": "Store tools are unavailable in this request."
    })


def uploads_dir():
    if os.getenv("RENDER") or using_sqlite():
        path = Path(os.getenv("UPLOAD_DIR", "/tmp/flower-uploads"))
    else:
        path = FRONTEND_DIR / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_extension(file):
    content_type = (file.mimetype or "").lower()
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension:
        return extension
    name = str(file.filename or "").lower()
    for suffix, ext in {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp", ".gif": ".gif"}.items():
        if name.endswith(suffix):
            return ext
    return None


def upsert_cart_item(connection, user_id, product_id, quantity):
    if using_sqlite():
        connection.execute(
            """
            INSERT INTO CartItems (UserId, ProductId, Quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(UserId, ProductId)
            DO UPDATE SET Quantity = Quantity + excluded.Quantity
            """,
            user_id,
            product_id,
            quantity,
        )
        return
    connection.execute(
        """
        MERGE dbo.CartItems AS target
        USING (SELECT ? AS UserId, ? AS ProductId) AS source
        ON target.UserId = source.UserId AND target.ProductId = source.ProductId
        WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + ?
        WHEN NOT MATCHED THEN INSERT (UserId, ProductId, Quantity)
            VALUES (source.UserId, source.ProductId, ?);
        """,
        user_id,
        product_id,
        quantity,
        quantity,
    )


def db_connection():
    if using_sqlite():
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return SqliteConnection(SQLITE_PATH)
    if pyodbc is None:
        raise RuntimeError("pyodbc is required for SQL Server on this machine.")
    return pyodbc.connect(connection_string(SQL_DATABASE))


@app.get('/api/ai/status')
def ai_status():
    return jsonify({
        'ai_provider': AI_PROVIDER,
        'ai_model': AI_MODEL,
        'has_api_key': bool(AI_API_KEY),
        'api_key_prefix': AI_API_KEY[:2] if AI_API_KEY else None,
    })


def validate_delivery_address(address):
    normalized = str(address or "").strip()
    if len(normalized) < 10:
        return None, "Enter a complete delivery address."
    if len(normalized) > MAX_DELIVERY_ADDRESS_LENGTH:
        return None, f"Delivery address must be {MAX_DELIVERY_ADDRESS_LENGTH} characters or fewer."
    return normalized, None


def initialize_sqlite():
    schema_statements = [
        """
        CREATE TABLE IF NOT EXISTS Users (
            Id TEXT NOT NULL PRIMARY KEY,
            Name TEXT NOT NULL,
            Email TEXT NOT NULL UNIQUE,
            PasswordHash BLOB NOT NULL,
            PasswordSalt BLOB NOT NULL,
            IsAdmin INTEGER NOT NULL DEFAULT 0,
            FavoriteFlowers TEXT NULL,
            FavoriteOccasion TEXT NULL,
            PreferredPaymentMethod TEXT NULL,
            PreferredAddressId TEXT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Products (
            Id TEXT NOT NULL PRIMARY KEY,
            Name TEXT NOT NULL,
            Price REAL NOT NULL,
            Category TEXT NOT NULL,
            Image TEXT NOT NULL,
            Description TEXT NOT NULL,
            CreatedByUserId TEXT NULL,
            StockQuantity INTEGER NOT NULL DEFAULT 10,
            IsGiftItem INTEGER NOT NULL DEFAULT 0,
            OccasionTags TEXT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Addresses (
            Id TEXT NOT NULL PRIMARY KEY,
            UserId TEXT NOT NULL,
            Label TEXT NOT NULL,
            Recipient TEXT NOT NULL,
            Line1 TEXT NOT NULL,
            City TEXT NOT NULL,
            State TEXT NOT NULL,
            PostalCode TEXT NOT NULL,
            Country TEXT NOT NULL,
            Phone TEXT NOT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Orders (
            Id TEXT NOT NULL PRIMARY KEY,
            UserId TEXT NOT NULL,
            Total REAL NOT NULL,
            DeliveryAddress TEXT NOT NULL DEFAULT '',
            DeliveryDate TEXT NULL,
            PaymentMethod TEXT NULL,
            PaymentStatus TEXT NOT NULL DEFAULT 'paid',
            Status TEXT NOT NULL,
            TrackingNumber TEXT NULL,
            UpdatedAt TEXT NULL,
            DeliveredAt TEXT NULL,
            CancelledAt TEXT NULL,
            GoogleAddress TEXT NULL,
            GoogleMapsUrl TEXT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (UserId) REFERENCES Users(Id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS OrderStatusEvents (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            OrderId TEXT NOT NULL,
            Status TEXT NOT NULL,
            Note TEXT NULL,
            Location TEXT NULL,
            CreatedByUserId TEXT NULL,
            EventType TEXT NOT NULL DEFAULT 'status',
            ActorRole TEXT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (OrderId) REFERENCES Orders(Id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS CartItems (
            UserId TEXT NOT NULL,
            ProductId TEXT NOT NULL,
            Quantity INTEGER NOT NULL CHECK (Quantity > 0),
            PRIMARY KEY (UserId, ProductId),
            FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE,
            FOREIGN KEY (ProductId) REFERENCES Products(Id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS OrderItems (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            OrderId TEXT NOT NULL,
            ProductId TEXT NOT NULL,
            ProductName TEXT NOT NULL,
            Price REAL NOT NULL,
            Quantity INTEGER NOT NULL CHECK (Quantity > 0),
            FOREIGN KEY (OrderId) REFERENCES Orders(Id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Sessions (
            TokenHash TEXT NOT NULL PRIMARY KEY,
            UserId TEXT NOT NULL,
            ExpiresAt TEXT NOT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS PasswordResets (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            UserId TEXT NOT NULL,
            TokenHash TEXT NOT NULL,
            ExpiresAt TEXT NOT NULL,
            UsedAt TEXT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS UX_Orders_TrackingNumber
            ON Orders(TrackingNumber)
            WHERE TrackingNumber IS NOT NULL
        """,
    ]
    with db_connection() as connection:
        for statement in schema_statements:
            connection.execute(statement)
        seed_catalog_and_admin(connection)
        connection.commit()


def seed_catalog_and_admin(connection):
    for product in PRODUCTS:
        exists = connection.execute(
            "SELECT 1 FROM dbo.Products WHERE Id = ?",
            product[0],
        ).fetchone()
        if not exists:
            connection.execute(
                """
                INSERT INTO dbo.Products
                    (Id, Name, Price, Category, Image, Description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                *product,
            )
    sync_catalog_prices(connection)
    sync_catalog_images(connection)
    admin = connection.execute(
        "SELECT Id FROM dbo.Users WHERE Email = ?", ADMIN_EMAIL
    ).fetchone()
    if admin:
        connection.execute(
            "UPDATE dbo.Users SET IsAdmin = 1 WHERE Id = ?", admin.Id
        )
    else:
        admin_id = "u_" + uuid.uuid4().hex[:16]
        salt, password_hash = hash_password(ADMIN_PASSWORD)
        connection.execute(
            """
            INSERT INTO dbo.Users
                (Id, Name, Email, PasswordHash, PasswordSalt, IsAdmin)
            VALUES (?, 'Store Admin', ?, ?, ?, 1)
            """,
            admin_id, ADMIN_EMAIL, password_hash, salt,
        )


def initialize_database():
    uploads_dir()
    if using_sqlite():
        initialize_sqlite()
        backfill_order_tracking()
        backfill_event_actors()
        return

    master = pyodbc.connect(connection_string("master"), autocommit=True)
    try:
        if not master.execute(
            "SELECT 1 FROM sys.databases WHERE name = ?", SQL_DATABASE
        ).fetchone():
            safe_name = SQL_DATABASE.replace("]", "]]")
            master.execute(f"CREATE DATABASE [{safe_name}]")
    finally:
        master.close()

    schema = """
    IF OBJECT_ID('dbo.Users', 'U') IS NULL
    CREATE TABLE dbo.Users (
        Id NVARCHAR(40) NOT NULL PRIMARY KEY,
        Name NVARCHAR(120) NOT NULL,
        Email NVARCHAR(255) NOT NULL UNIQUE,
        PasswordHash VARBINARY(32) NOT NULL,
        PasswordSalt VARBINARY(16) NOT NULL,
        IsAdmin BIT NOT NULL DEFAULT 0,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );

    IF COL_LENGTH('dbo.Users', 'IsAdmin') IS NULL
        ALTER TABLE dbo.Users ADD IsAdmin BIT NOT NULL
            CONSTRAINT DF_Users_IsAdmin DEFAULT 0;

    IF COL_LENGTH('dbo.Users', 'FavoriteFlowers') IS NULL
        ALTER TABLE dbo.Users ADD FavoriteFlowers NVARCHAR(500) NULL;

    IF COL_LENGTH('dbo.Users', 'FavoriteOccasion') IS NULL
        ALTER TABLE dbo.Users ADD FavoriteOccasion NVARCHAR(200) NULL;

    IF COL_LENGTH('dbo.Users', 'PreferredPaymentMethod') IS NULL
        ALTER TABLE dbo.Users ADD PreferredPaymentMethod NVARCHAR(50) NULL;

    IF COL_LENGTH('dbo.Users', 'PreferredAddressId') IS NULL
        ALTER TABLE dbo.Users ADD PreferredAddressId NVARCHAR(40) NULL;

    IF OBJECT_ID('dbo.Products', 'U') IS NULL
    CREATE TABLE dbo.Products (
        Id NVARCHAR(40) NOT NULL PRIMARY KEY,
        Name NVARCHAR(150) NOT NULL,
        Price DECIMAL(10,2) NOT NULL,
        Category NVARCHAR(80) NOT NULL,
        Image NVARCHAR(1000) NOT NULL,
        Description NVARCHAR(1000) NOT NULL,
        CreatedByUserId NVARCHAR(40) NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );

    IF COL_LENGTH('dbo.Products', 'CreatedByUserId') IS NULL
        ALTER TABLE dbo.Products ADD CreatedByUserId NVARCHAR(40) NULL;

    IF COL_LENGTH('dbo.Products', 'CreatedAt') IS NULL
        ALTER TABLE dbo.Products ADD CreatedAt DATETIME2 NOT NULL
            CONSTRAINT DF_Products_CreatedAt DEFAULT SYSUTCDATETIME();

    IF COL_LENGTH('dbo.Products', 'StockQuantity') IS NULL
        ALTER TABLE dbo.Products ADD StockQuantity INT NOT NULL
            CONSTRAINT DF_Products_StockQuantity DEFAULT 10;

    IF COL_LENGTH('dbo.Products', 'IsGiftItem') IS NULL
        ALTER TABLE dbo.Products ADD IsGiftItem BIT NOT NULL
            CONSTRAINT DF_Products_IsGiftItem DEFAULT 0;

    IF COL_LENGTH('dbo.Products', 'OccasionTags') IS NULL
        ALTER TABLE dbo.Products ADD OccasionTags NVARCHAR(200) NULL;

    IF OBJECT_ID('dbo.Addresses', 'U') IS NULL
    CREATE TABLE dbo.Addresses (
        Id NVARCHAR(40) NOT NULL PRIMARY KEY,
        UserId NVARCHAR(40) NOT NULL,
        Label NVARCHAR(100) NOT NULL,
        Recipient NVARCHAR(100) NOT NULL,
        Line1 NVARCHAR(200) NOT NULL,
        City NVARCHAR(100) NOT NULL,
        State NVARCHAR(100) NOT NULL,
        PostalCode NVARCHAR(20) NOT NULL,
        Country NVARCHAR(100) NOT NULL,
        Phone NVARCHAR(40) NOT NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Addresses_Users FOREIGN KEY (UserId) REFERENCES dbo.Users(Id) ON DELETE CASCADE
    );

    IF OBJECT_ID('dbo.Orders', 'U') IS NULL
    CREATE TABLE dbo.Orders (
        Id NVARCHAR(40) NOT NULL PRIMARY KEY,
        UserId NVARCHAR(40) NOT NULL,
        Total DECIMAL(10,2) NOT NULL,
        DeliveryAddress NVARCHAR(1000) NOT NULL DEFAULT '',
        DeliveryDate DATETIME2 NULL,
        PaymentMethod NVARCHAR(50) NULL,
        Status NVARCHAR(30) NOT NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Orders_Users FOREIGN KEY (UserId) REFERENCES dbo.Users(Id)
    );

    IF COL_LENGTH('dbo.Orders', 'DeliveryDate') IS NULL
        ALTER TABLE dbo.Orders ADD DeliveryDate DATETIME2 NULL;

    IF COL_LENGTH('dbo.Orders', 'PaymentMethod') IS NULL
        ALTER TABLE dbo.Orders ADD PaymentMethod NVARCHAR(50) NULL;

    IF COL_LENGTH('dbo.Orders', 'PaymentStatus') IS NULL
        ALTER TABLE dbo.Orders ADD PaymentStatus NVARCHAR(20) NOT NULL
            CONSTRAINT DF_Orders_PaymentStatus DEFAULT 'paid';

    IF COL_LENGTH('dbo.Orders', 'TrackingNumber') IS NULL
        ALTER TABLE dbo.Orders ADD TrackingNumber NVARCHAR(32) NULL;

    IF COL_LENGTH('dbo.Orders', 'UpdatedAt') IS NULL
        ALTER TABLE dbo.Orders ADD UpdatedAt DATETIME2 NULL;

    IF COL_LENGTH('dbo.Orders', 'DeliveredAt') IS NULL
        ALTER TABLE dbo.Orders ADD DeliveredAt DATETIME2 NULL;

    IF COL_LENGTH('dbo.Orders', 'CancelledAt') IS NULL
        ALTER TABLE dbo.Orders ADD CancelledAt DATETIME2 NULL;

    IF COL_LENGTH('dbo.Orders', 'GoogleAddress') IS NULL
        ALTER TABLE dbo.Orders ADD GoogleAddress NVARCHAR(500) NULL;

    IF COL_LENGTH('dbo.Orders', 'GoogleMapsUrl') IS NULL
        ALTER TABLE dbo.Orders ADD GoogleMapsUrl NVARCHAR(500) NULL;

    IF OBJECT_ID('dbo.OrderStatusEvents', 'U') IS NULL
    CREATE TABLE dbo.OrderStatusEvents (
        Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        OrderId NVARCHAR(40) NOT NULL,
        Status NVARCHAR(30) NOT NULL,
        Note NVARCHAR(500) NULL,
        Location NVARCHAR(200) NULL,
        CreatedByUserId NVARCHAR(40) NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_OrderStatusEvents_Orders FOREIGN KEY (OrderId)
            REFERENCES dbo.Orders(Id) ON DELETE CASCADE
    );

    IF OBJECT_ID('dbo.CartItems', 'U') IS NULL
    CREATE TABLE dbo.CartItems (
        UserId NVARCHAR(40) NOT NULL,
        ProductId NVARCHAR(40) NOT NULL,
        Quantity INT NOT NULL CHECK (Quantity > 0),
        CONSTRAINT PK_CartItems PRIMARY KEY (UserId, ProductId),
        CONSTRAINT FK_CartItems_Users FOREIGN KEY (UserId) REFERENCES dbo.Users(Id) ON DELETE CASCADE,
        CONSTRAINT FK_CartItems_Products FOREIGN KEY (ProductId) REFERENCES dbo.Products(Id)
    );

    IF OBJECT_ID('dbo.OrderItems', 'U') IS NULL
    CREATE TABLE dbo.OrderItems (
        Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        OrderId NVARCHAR(40) NOT NULL,
        ProductId NVARCHAR(40) NOT NULL,
        ProductName NVARCHAR(150) NOT NULL,
        Price DECIMAL(10,2) NOT NULL,
        Quantity INT NOT NULL CHECK (Quantity > 0),
        CONSTRAINT FK_OrderItems_Orders FOREIGN KEY (OrderId) REFERENCES dbo.Orders(Id) ON DELETE CASCADE
    );

    IF OBJECT_ID('dbo.Sessions', 'U') IS NULL
    CREATE TABLE dbo.Sessions (
        TokenHash CHAR(64) NOT NULL PRIMARY KEY,
        UserId NVARCHAR(40) NOT NULL,
        ExpiresAt DATETIME2 NOT NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Sessions_Users FOREIGN KEY (UserId) REFERENCES dbo.Users(Id) ON DELETE CASCADE
    );

    IF OBJECT_ID('dbo.PasswordResets', 'U') IS NULL
    CREATE TABLE dbo.PasswordResets (
        Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        UserId NVARCHAR(40) NOT NULL,
        TokenHash CHAR(64) NOT NULL,
        ExpiresAt DATETIME2 NOT NULL,
        UsedAt DATETIME2 NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PasswordResets_Users FOREIGN KEY (UserId) REFERENCES dbo.Users(Id) ON DELETE CASCADE
    );
    """

    with db_connection() as connection:
        connection.execute(schema)
        connection.execute(
            """
            IF COL_LENGTH('dbo.OrderStatusEvents', 'EventType') IS NULL
                ALTER TABLE dbo.OrderStatusEvents ADD EventType NVARCHAR(20) NOT NULL
                    CONSTRAINT DF_OrderStatusEvents_EventType DEFAULT 'status';
            """
        )
        connection.execute(
            """
            IF COL_LENGTH('dbo.OrderStatusEvents', 'ActorRole') IS NULL
                ALTER TABLE dbo.OrderStatusEvents ADD ActorRole NVARCHAR(20) NULL;
            """
        )
        connection.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes
                WHERE name = 'UX_Orders_TrackingNumber'
                  AND object_id = OBJECT_ID('dbo.Orders')
            )
            AND COL_LENGTH('dbo.Orders', 'TrackingNumber') IS NOT NULL
                CREATE UNIQUE INDEX UX_Orders_TrackingNumber
                    ON dbo.Orders(TrackingNumber)
                    WHERE TrackingNumber IS NOT NULL;
            """
        )
        seed_catalog_and_admin(connection)
        connection.commit()

    backfill_order_tracking()
    backfill_event_actors()


def backfill_order_tracking():
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT o.Id, o.Status, o.CreatedAt
            FROM dbo.Orders o
            WHERE o.TrackingNumber IS NULL OR o.TrackingNumber = ''
            """
        ).fetchall()
        for row in rows:
            tracking_number = generate_tracking_number(connection)
            connection.execute(
                """
                UPDATE dbo.Orders
                SET TrackingNumber = ?, UpdatedAt = COALESCE(UpdatedAt, CreatedAt)
                WHERE Id = ?
                """,
                tracking_number, row.Id,
            )
            if not connection.execute(
                "SELECT 1 FROM dbo.OrderStatusEvents WHERE OrderId = ?",
                row.Id,
            ).fetchone():
                record_order_status_event(
                    connection,
                    row.Id,
                    row.Status or "confirmed",
                    "Order imported into tracking system.",
                    "Petal & Stem",
                    None,
                )
        connection.commit()


def backfill_event_actors():
    with db_connection() as connection:
        if using_sqlite():
            connection.execute(
                """
                UPDATE OrderStatusEvents
                SET ActorRole = CASE
                    WHEN CreatedByUserId IS NULL THEN 'system'
                    WHEN CreatedByUserId = (
                        SELECT UserId FROM Orders WHERE Orders.Id = OrderStatusEvents.OrderId
                    ) THEN 'buyer'
                    ELSE 'seller'
                END
                WHERE ActorRole IS NULL OR ActorRole = ''
                """
            )
            connection.commit()
            return
        if connection.execute(
            """
            SELECT 1
            FROM sys.columns
            WHERE object_id = OBJECT_ID('dbo.OrderStatusEvents')
              AND name = 'ActorRole'
            """
        ).fetchone():
            connection.execute(
                """
                UPDATE e
                SET e.ActorRole = CASE
                    WHEN e.CreatedByUserId IS NULL THEN 'system'
                    WHEN e.CreatedByUserId = o.UserId THEN 'buyer'
                    ELSE 'seller'
                END
                FROM dbo.OrderStatusEvents e
                JOIN dbo.Orders o ON o.Id = e.OrderId
                WHERE e.ActorRole IS NULL OR e.ActorRole = ''
                """
            )
        connection.commit()


def generate_tracking_number(connection):
    while True:
        tracking_number = (
            f"PS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
            f"{secrets.token_hex(4).upper()}"
        )
        exists = connection.execute(
            "SELECT 1 FROM dbo.Orders WHERE TrackingNumber = ?",
            tracking_number,
        ).fetchone()
        if not exists:
            return tracking_number


def utc_iso(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def normalize_order_status(status):
    normalized = str(status or "").strip().lower()
    if normalized not in ORDER_STATUSES:
        raise ValueError(f"Invalid order status: {status}")
    return normalized


def normalize_payment_status(status):
    normalized = str(status or "pending").strip().lower()
    if normalized not in PAYMENT_STATUSES:
        return "pending"
    return normalized


def normalize_payment_method(method):
    normalized = str(method or "online").strip().lower().replace("-", "_")
    if normalized in {"cash", "cash_in_hand", "cod", "cash_on_delivery"}:
        return "cash"
    return "online"


def checkout_payment_status(payment_method):
    return "pending"


def seller_next_status(current_status):
    return SELLER_NEXT_STATUS.get(normalize_order_status(current_status))


def seller_advance_action_label(next_status):
    return SELLER_ADVANCE_ACTIONS.get(
        normalize_order_status(next_status),
        DISPLAY_ORDER_STATUS_LABELS.get(
            normalize_order_status(next_status),
            next_status.replace("_", " ").title(),
        ),
    )


def enrich_seller_order_flags(payload, order_row):
    payment_status = normalize_payment_status(
        getattr(order_row, "PaymentStatus", None) or "pending"
    )
    current_status = normalize_order_status(order_row.Status)
    next_status = seller_next_status(current_status)
    payload["canAccept"] = current_status == "pending"
    payload["canAcceptPayment"] = payment_status == "pending"
    # Delivery steps are independent of payment — seller can deliver before payment is marked paid.
    payload["canAdvance"] = bool(next_status)
    if next_status:
        payload["nextStatus"] = next_status
        payload["nextStatusLabel"] = ORDER_STATUSES.get(
            next_status, next_status.replace("_", " ").title()
        )
        payload["nextStatusAction"] = seller_advance_action_label(next_status)
    return payload


def can_transition_status(current_status, next_status):
    current = normalize_order_status(current_status)
    next_value = normalize_order_status(next_status)
    return next_value in ORDER_TRANSITIONS.get(current, set())


def get_order_items(connection, order_id):
    return get_order_items_enriched(connection, order_id)


def get_order_items_enriched(connection, order_id):
    rows = connection.execute(
        """
        SELECT oi.ProductId, oi.ProductName, oi.Price, oi.Quantity,
               p.Image, p.CreatedByUserId, seller.Name AS SellerName
        FROM dbo.OrderItems oi
        LEFT JOIN dbo.Products p ON p.Id = oi.ProductId
        LEFT JOIN dbo.Users seller ON seller.Id = p.CreatedByUserId
        WHERE oi.OrderId = ?
        ORDER BY oi.Id
        """,
        order_id,
    ).fetchall()
    return [
        {
            "productId": item.ProductId,
            "name": item.ProductName,
            "price": float(item.Price),
            "qty": item.Quantity,
            "image": item.Image or "",
            "sellerName": item.SellerName or "Petal & Stem",
            "lineTotal": round(float(item.Price) * item.Quantity, 2),
        }
        for item in rows
    ]


def resolve_actor_role(connection, order_row, actor_user_id, explicit_role=None):
    if explicit_role in ACTOR_ROLE_LABELS:
        return explicit_role
    if not actor_user_id:
        return "system"
    if order_row and actor_user_id == order_row.UserId:
        return "buyer"
    actor = connection.execute(
        "SELECT IsAdmin FROM dbo.Users WHERE Id = ?",
        actor_user_id,
    ).fetchone()
    if actor and actor.IsAdmin:
        return "admin"
    if order_row and seller_owns_order(connection, order_row.Id, actor_user_id):
        return "seller"
    return "seller"


def tracking_location_for(status, delivery_address=None, location=None):
    custom = str(location or "").strip()
    if custom:
        return custom[:200]
    city = extract_delivery_city(delivery_address)
    if status == "out_for_delivery" and city:
        return f"On the way to {city}"
    if status == "delivered" and city:
        return city
    return STATUS_EVENT_LOCATIONS.get(status, "Petal & Stem")


def event_label(event_type, status):
    if event_type == "note":
        return "Message"
    if event_type == "payment":
        return "Payment update"
    return DISPLAY_ORDER_STATUS_LABELS.get(
        status,
        ORDER_STATUSES.get(status, str(status or "Update").replace("_", " ").title()),
    )


def get_order_status_events(connection, order_id):
    rows = connection.execute(
        """
        SELECT e.Status, e.Note, e.Location, e.CreatedAt, e.CreatedByUserId,
               e.EventType, e.ActorRole, actor.Name AS ActorName
        FROM dbo.OrderStatusEvents e
        LEFT JOIN dbo.Users actor ON actor.Id = e.CreatedByUserId
        WHERE e.OrderId = ?
        ORDER BY e.CreatedAt ASC, e.Id ASC
        """,
        order_id,
    ).fetchall()
    events = []
    for row in rows:
        event_type = str(getattr(row, "EventType", None) or "status").strip().lower()
        if event_type not in EVENT_TYPES:
            event_type = "status"
        status = str(row.Status or "").strip().lower()
        actor_role = str(getattr(row, "ActorRole", None) or "").strip().lower()
        if actor_role not in ACTOR_ROLE_LABELS:
            actor_role = "system"
        events.append({
            "status": status,
            "label": event_label(event_type, status),
            "note": row.Note,
            "location": row.Location,
            "createdAt": utc_iso(row.CreatedAt),
            "eventType": event_type,
            "actorRole": actor_role,
            "actorName": row.ActorName,
            "actorLabel": ACTOR_ROLE_LABELS.get(actor_role, "Update"),
        })
    return events


def record_order_status_event(
    connection,
    order_id,
    status,
    note=None,
    location=None,
    actor_user_id=None,
    actor_role=None,
    event_type="status",
):
    event_type = str(event_type or "status").strip().lower()
    if event_type not in EVENT_TYPES:
        event_type = "status"
    order_row = fetch_order_row(connection, order_id)
    current_status = normalize_order_status(
        status if event_type == "status" else (order_row.Status if order_row else "pending")
    )
    role = resolve_actor_role(connection, order_row, actor_user_id, actor_role)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    clean_note = str(note or "").strip() or None
    clean_location = tracking_location_for(
        current_status,
        getattr(order_row, "DeliveryAddress", None) if order_row else None,
        location,
    )
    connection.execute(
        """
        INSERT INTO dbo.OrderStatusEvents
            (OrderId, Status, Note, Location, CreatedByUserId, EventType, ActorRole)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        order_id,
        current_status,
        clean_note,
        clean_location,
        actor_user_id,
        event_type,
        role,
    )
    updates = ["UpdatedAt = ?"]
    params = [now]
    if event_type == "status":
        updates.insert(0, "Status = ?")
        params.insert(0, current_status)
        if current_status == "delivered":
            updates.append("DeliveredAt = ?")
            params.append(now)
        if current_status == "cancelled":
            updates.append("CancelledAt = ?")
            params.append(now)
            connection.execute(
                """
                UPDATE dbo.Orders
                SET PaymentStatus = 'refunded'
                WHERE Id = ? AND PaymentStatus = 'paid'
                """,
                order_id,
            )
        if current_status == "refunded":
            connection.execute(
                """
                UPDATE dbo.Orders
                SET PaymentStatus = 'refunded'
                WHERE Id = ?
                """,
                order_id,
            )
    params.append(order_id)
    connection.execute(
        f"UPDATE dbo.Orders SET {', '.join(updates)} WHERE Id = ?",
        *params,
    )
    return current_status


def parse_tracking_note(raw_note, max_length=400):
    note = str(raw_note or "").strip()
    if not note:
        return None
    if len(note) > max_length:
        raise ValueError(f"Note must be {max_length} characters or fewer.")
    return note


def estimate_delivery_at(order_row, status):
    if status == "delivered":
        return utc_iso(order_row.DeliveredAt)
    if status in TERMINAL_STATUSES:
        return None
    if getattr(order_row, "DeliveryDate", None):
        return utc_iso(order_row.DeliveryDate)
    created = order_row.CreatedAt
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if not created:
        created = datetime.now(timezone.utc)
    offsets = {
        "pending": 2,
        "confirmed": 2,
        "preparing": 1,
        "out_for_delivery": 0,
    }
    days = offsets.get(status, 2)
    if days == 0:
        return (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    return (created + timedelta(days=days)).isoformat()


def fetch_order_row(connection, order_id):
    return connection.execute(
        f"""
        {ORDER_SELECT_SQL}
        WHERE o.Id = ?
        """,
        order_id,
    ).fetchone()


def fetch_order_by_tracking(connection, tracking_number):
    normalized = str(tracking_number or "").strip().upper()
    if not normalized:
        return None
    return connection.execute(
        f"""
        {ORDER_SELECT_SQL}
        WHERE o.TrackingNumber = ?
        """,
        normalized,
    ).fetchone()


def build_order_progress(current_status, events):
    completed_statuses = {
        event["status"]
        for event in events
        if event.get("eventType", "status") == "status"
        and event["status"] in ORDER_STATUS_FLOW
    }
    if current_status in ORDER_STATUS_FLOW:
        current_index = ORDER_STATUS_FLOW.index(current_status)
        return [
            {
                "status": step,
                "label": ORDER_STATUSES[step],
                "complete": ORDER_STATUS_FLOW.index(step) < current_index,
                "current": step == current_status,
            }
            for step in ORDER_STATUS_FLOW
        ]
    return [
        {
            "status": step,
            "label": ORDER_STATUSES[step],
            "complete": step in completed_statuses,
            "current": False,
        }
        for step in ORDER_STATUS_FLOW
    ]


def build_tracking_payload(connection, order_row, *, include_private_fields=True):
    items = get_order_items(connection, order_row.Id)
    events = get_order_status_events(connection, order_row.Id)
    current_status = normalize_order_status(order_row.Status)
    payment_status = normalize_payment_status(
        getattr(order_row, "PaymentStatus", None) or "pending"
    )
    payment_method = normalize_payment_method(
        getattr(order_row, "PaymentMethod", None) or "online"
    )
    last_scan = next(
        (
            event
            for event in reversed(events)
            if event.get("eventType") in {"status", "payment"}
        ),
        events[-1] if events else None,
    )
    seller_names = []
    for item in items:
        name = str(item.get("sellerName") or "").strip()
        if name and name not in seller_names:
            seller_names.append(name)
    payload = {
        "id": order_row.Id,
        "trackingNumber": order_row.TrackingNumber,
        "status": current_status,
        "statusLabel": DISPLAY_ORDER_STATUS_LABELS.get(
            current_status,
            ORDER_STATUSES.get(current_status, current_status.title()),
        ),
        "paymentStatus": payment_status,
        "paymentStatusLabel": PAYMENT_STATUSES.get(
            payment_status, payment_status.title()
        ),
        "paymentMethod": payment_method,
        "paymentMethodLabel": PAYMENT_METHODS.get(
            payment_method, payment_method.replace("_", " ").title()
        ),
        "createdAt": utc_iso(order_row.CreatedAt),
        "updatedAt": utc_iso(order_row.UpdatedAt),
        "deliveredAt": utc_iso(order_row.DeliveredAt),
        "cancelledAt": utc_iso(order_row.CancelledAt),
        "deliveryDate": utc_iso(order_row.DeliveryDate),
        "eta": estimate_delivery_at(order_row, current_status),
        "currentLocation": (last_scan or {}).get("location"),
        "lastScan": last_scan,
        "sellerName": ", ".join(seller_names) or "Petal & Stem",
        "timeline": events,
        "progress": build_order_progress(current_status, events),
        "canCancel": current_status in CANCELLABLE_STATUSES,
        "canPostNote": current_status not in {"cancelled", "refunded"},
        "isTerminal": current_status in TERMINAL_STATUSES,
    }
    if include_private_fields:
        payload.update({
            "userId": order_row.UserId,
            "customerName": order_row.Name,
            "customerEmail": order_row.Email,
            "buyerName": order_row.Name,
            "buyerEmail": order_row.Email,
            "items": items,
            "total": float(order_row.Total),
            "deliveryAddress": order_row.DeliveryAddress,
        })
    else:
        payload.update({
            "itemCount": sum(item["qty"] for item in items),
            "itemsSummary": ", ".join(
                f'{item["qty"]} x {item["name"]}' for item in items[:3]
            ),
            "deliveryCity": extract_delivery_city(order_row.DeliveryAddress),
        })
    return payload


def extract_delivery_city(address):
    parts = [part.strip() for part in str(address or "").split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else "Delivery address on file"


def create_order_record(
    connection,
    user_id,
    items,
    total,
    delivery_address,
    delivery_date=None,
    payment_method=None,
    payment_status="paid",
):
    order_id = "o_" + uuid.uuid4().hex[:12]
    tracking_number = generate_tracking_number(connection)
    payment_method = normalize_payment_method(payment_method)
    payment_status = normalize_payment_status(payment_status)
    connection.execute(
        """
        INSERT INTO dbo.Orders
            (Id, UserId, Total, DeliveryAddress, DeliveryDate, PaymentMethod,
             PaymentStatus, Status, TrackingNumber, UpdatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, SYSUTCDATETIME())
        """,
        order_id,
        user_id,
        total,
        delivery_address,
        delivery_date,
        payment_method,
        payment_status,
        tracking_number,
    )
    for item in items:
        connection.execute(
            """
            INSERT INTO dbo.OrderItems
                (OrderId, ProductId, ProductName, Price, Quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            order_id,
            item["id"],
            item["name"],
            item["price"],
            item["qty"],
        )
    record_order_status_event(
        connection,
        order_id,
        "pending",
        STATUS_EVENT_NOTES["pending"],
        tracking_location_for("pending", delivery_address),
        user_id,
        actor_role="buyer",
        event_type="status",
    )
    return order_id, tracking_number


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 310_000
    )
    return salt, password_hash


def as_bytes(value):
    if value is None:
        return b""
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return bytes(value)


def db_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def db_datetime(value):
    if value is None:
        return None
    if using_sqlite():
        if isinstance(value, str):
            return value
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def show_reset_code_in_response():
    return bool(os.getenv("RENDER")) or os.getenv(
        "SHOW_RESET_CODE", ""
    ).strip().lower() in {"1", "true", "yes"}


def public_user(row):
    return {
        "id": row.Id,
        "name": row.Name,
        "email": row.Email,
        "isAdmin": bool(row.IsAdmin),
    }


def create_session(connection, user_id):
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = db_datetime(db_now() + timedelta(days=7))
    connection.execute(
        "INSERT INTO dbo.Sessions (TokenHash, UserId, ExpiresAt) VALUES (?, ?, ?)",
        token_hash, user_id, expires_at,
    )
    return token


def bearer_token():
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else None


def current_user(connection):
    token = bearer_token()
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return connection.execute(
        """
        SELECT u.Id, u.Name, u.Email, u.IsAdmin
        FROM dbo.Sessions s
        JOIN dbo.Users u ON u.Id = s.UserId
        WHERE s.TokenHash = ? AND s.ExpiresAt > SYSUTCDATETIME()
        """,
        token_hash,
    ).fetchone()


def product_json(row, viewer_id=None):
    created_by = getattr(row, "CreatedByUserId", None)
    creator_name = getattr(row, "CreatorName", None)
    stock_quantity = getattr(row, "StockQuantity", 10)
    is_gift = bool(getattr(row, "IsGiftItem", False))
    occasion_tags = getattr(row, "OccasionTags", None)
    is_user_created = bool(created_by)
    if is_user_created and viewer_id and created_by == viewer_id:
        creator_label = "You"
    elif creator_name:
        creator_label = creator_name
    else:
        creator_label = None
    return {
        "id": row.Id,
        "name": row.Name,
        "price": float(row.Price),
        "category": row.Category,
        "image": row.Image,
        "description": row.Description,
        "createdBy": created_by,
        "creatorName": creator_label,
        "isUserCreated": is_user_created,
        "isMine": bool(viewer_id and created_by and created_by == viewer_id),
        "stockQuantity": stock_quantity,
        "isGiftItem": is_gift,
        "occasionTags": occasion_tags,
    }


def is_purchasable_product(connection, product_id, buyer_id=None):
    row = connection.execute(
        "SELECT CreatedByUserId FROM dbo.Products WHERE Id = ?",
        product_id,
    ).fetchone()
    if not row:
        return False, "Product not found."
    if buyer_id and row.CreatedByUserId and row.CreatedByUserId == buyer_id:
        return False, "You cannot order your own product."
    return True, None


def validate_cart_for_checkout(connection, user_id, items):
    for item in items:
        product_id = item.get("id") or item.get("productId")
        if not product_id:
            continue
        purchasable, error = is_purchasable_product(connection, product_id, user_id)
        if not purchasable:
            return False, error
    return True, None


PRODUCT_SELECT_SQL = """
    SELECT p.Id, p.Name, p.Price, p.Category, p.Image, p.Description,
           p.CreatedByUserId, creator.Name AS CreatorName
    FROM dbo.Products p
    LEFT JOIN dbo.Users creator ON creator.Id = p.CreatedByUserId
"""


def get_seller_orders(connection, seller_id, status_filter=None):
    query = """
        SELECT o.Id
        FROM dbo.Orders o
        JOIN dbo.OrderItems oi ON oi.OrderId = o.Id
        JOIN dbo.Products p ON p.Id = oi.ProductId
        WHERE p.CreatedByUserId = ?
    """
    params = [seller_id]
    if status_filter == "received":
        query += " AND o.Status NOT IN ('delivered', 'cancelled', 'refunded')"
    elif status_filter:
        query += " AND o.Status = ?"
        params.append(status_filter)
    query += " GROUP BY o.Id, o.CreatedAt ORDER BY o.CreatedAt DESC"
    order_ids = connection.execute(query, *params).fetchall()
    orders = []
    for row in order_ids:
        order_row = fetch_order_row(connection, row.Id)
        if not order_row:
            continue
        items = get_order_items(connection, order_row.Id)
        seller_items = []
        seller_subtotal = 0.0
        for item in items:
            product_row = connection.execute(
                """
                SELECT p.CreatedByUserId, p.Image
                FROM dbo.Products p
                WHERE p.Id = ?
                """,
                item["productId"],
            ).fetchone()
            if product_row and product_row.CreatedByUserId == seller_id:
                enriched = {
                    **item,
                    "image": item.get("image") or getattr(product_row, "Image", "") or "",
                }
                seller_items.append(enriched)
                seller_subtotal += item["lineTotal"]
        if not seller_items:
            continue
        payload = build_tracking_payload(connection, order_row)
        payload["buyerName"] = order_row.Name
        payload["buyerEmail"] = order_row.Email
        payload["sellerItems"] = seller_items
        payload["sellerSubtotal"] = round(seller_subtotal, 2)
        enrich_seller_order_flags(payload, order_row)
        orders.append(payload)
    return orders


def seller_owns_order(connection, order_id, seller_id):
    return connection.execute(
        """
        SELECT 1
        FROM dbo.OrderItems oi
        JOIN dbo.Products p ON p.Id = oi.ProductId
        WHERE oi.OrderId = ? AND p.CreatedByUserId = ?
        """,
        order_id,
        seller_id,
    ).fetchone()


def address_json(row):
    return {
        "id": row.Id,
        "label": row.Label,
        "recipient": row.Recipient,
        "line1": row.Line1,
        "city": row.City,
        "state": row.State,
        "postalCode": row.PostalCode,
        "country": row.Country,
        "phone": row.Phone,
    }


def require_user(connection):
    user = current_user(connection)
    if not user:
        return None, (jsonify(error="Please log in first."), 401)
    return user, None


def require_admin(connection):
    user, error = require_user(connection)
    if error:
        return None, error
    if not user.IsAdmin:
        return None, (jsonify(error="Admin access required."), 403)
    return user, None


def owned_product(connection, product_id, user_id):
    return connection.execute(
        """
        SELECT Id, Name, Price, Category, Image, Description, CreatedByUserId
        FROM dbo.Products
        WHERE Id = ? AND CreatedByUserId = ?
        """,
        product_id, user_id,
    ).fetchone()


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not name or not email or not password:
        return jsonify(error="Name, email, and password are required."), 400
    if len(password) < 6:
        return jsonify(error="Password must be at least 6 characters."), 400

    with db_connection() as connection:
        if connection.execute(
            "SELECT 1 FROM dbo.Users WHERE Email = ?", email
        ).fetchone():
            return jsonify(error="An account with this email already exists."), 409
        user_id = "u_" + uuid.uuid4().hex[:16]
        salt, password_hash = hash_password(password)
        connection.execute(
            """
            INSERT INTO dbo.Users
                (Id, Name, Email, PasswordHash, PasswordSalt, IsAdmin)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            user_id, name, email, password_hash, salt,
        )
        token = create_session(connection, user_id)
        connection.commit()
        return jsonify(
            token=token,
            user={"id": user_id, "name": name, "email": email, "isAdmin": False},
        ), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or not password:
        return jsonify(error="Email and password are required."), 400

    with db_connection() as connection:
        user = connection.execute(
            """
            SELECT Id, Name, Email, PasswordHash, PasswordSalt, IsAdmin
            FROM dbo.Users WHERE Email = ?
            """,
            email,
        ).fetchone()
        if not user:
            return jsonify(
                error="No account found for this email. Sign up first or use Forgot password."
            ), 401
        _, candidate_hash = hash_password(password, as_bytes(user.PasswordSalt))
        if not hmac.compare_digest(candidate_hash, as_bytes(user.PasswordHash)):
            return jsonify(error="Invalid email or password."), 401
        token = create_session(connection, user.Id)
        connection.commit()
        return jsonify(token=token, user=public_user(user))


@app.post("/api/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    if not email:
        return jsonify(error="Email is required."), 400

    response = {
        "message": "If an account exists for that email, use the reset code to choose a new password.",
    }
    with db_connection() as connection:
        user = connection.execute(
            "SELECT Id, Email FROM dbo.Users WHERE Email = ?",
            email,
        ).fetchone()
        if not user:
            return jsonify(response)

        reset_code = f"{secrets.randbelow(1_000_000):06d}"
        token_hash = hashlib.sha256(reset_code.encode("utf-8")).hexdigest()
        expires_at = db_datetime(db_now() + timedelta(minutes=15))
        connection.execute(
            "UPDATE dbo.PasswordResets SET UsedAt = ? WHERE UserId = ? AND UsedAt IS NULL",
            db_datetime(db_now()),
            user.Id,
        )
        connection.execute(
            """
            INSERT INTO dbo.PasswordResets (UserId, TokenHash, ExpiresAt)
            VALUES (?, ?, ?)
            """,
            user.Id,
            token_hash,
            expires_at,
        )
        connection.commit()
        if show_reset_code_in_response():
            response["resetCode"] = reset_code
            response["message"] = (
                "Use this reset code within 15 minutes to choose a new password."
            )
        return jsonify(response)


@app.post("/api/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    code = str(data.get("code", "") or "").strip()
    password = str(data.get("password", "") or "")
    if not email or not code or not password:
        return jsonify(error="Email, reset code, and new password are required."), 400
    if len(password) < 6:
        return jsonify(error="Password must be at least 6 characters."), 400

    token_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    with db_connection() as connection:
        user = connection.execute(
            "SELECT Id FROM dbo.Users WHERE Email = ?",
            email,
        ).fetchone()
        if not user:
            return jsonify(error="Invalid reset code or email."), 400

        reset_row = connection.execute(
            """
            SELECT Id
            FROM dbo.PasswordResets
            WHERE UserId = ? AND TokenHash = ? AND UsedAt IS NULL
              AND ExpiresAt > SYSUTCDATETIME()
            ORDER BY Id DESC
            """,
            user.Id,
            token_hash,
        ).fetchone()
        if not reset_row:
            return jsonify(error="Invalid or expired reset code."), 400

        salt, password_hash = hash_password(password)
        connection.execute(
            """
            UPDATE dbo.Users
            SET PasswordHash = ?, PasswordSalt = ?
            WHERE Id = ?
            """,
            password_hash,
            salt,
            user.Id,
        )
        connection.execute(
            """
            UPDATE dbo.PasswordResets
            SET UsedAt = ?
            WHERE Id = ?
            """,
            db_datetime(db_now()),
            reset_row.Id,
        )
        connection.execute(
            "DELETE FROM dbo.Sessions WHERE UserId = ?",
            user.Id,
        )
        connection.commit()
        return jsonify(message="Password updated. You can log in with your new password.")


@app.post("/api/logout")
def logout():
    token = bearer_token()
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with db_connection() as connection:
            connection.execute(
                "DELETE FROM dbo.Sessions WHERE TokenHash = ?", token_hash
            )
            connection.commit()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Not logged in."), 401
        return jsonify(user=public_user(user))


@app.get("/api/products")
def products():
    with db_connection() as connection:
        user = current_user(connection)
        viewer_id = user.Id if user else None
        rows = connection.execute(
            f"""
            {PRODUCT_SELECT_SQL}
            ORDER BY p.CreatedAt DESC, p.Name
            """
        ).fetchall()
        return jsonify(products=[product_json(row, viewer_id) for row in rows])


@app.get("/api/products/mine")
def my_products():
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        rows = connection.execute(
            f"""
            {PRODUCT_SELECT_SQL}
            WHERE p.CreatedByUserId = ?
            ORDER BY p.CreatedAt DESC, p.Name
            """,
            user.Id,
        ).fetchall()
        return jsonify(products=[product_json(row, user.Id) for row in rows])


@app.get("/api/products/mine/orders")
def seller_orders():
    status_filter = str(request.args.get("status", "") or "").strip().lower()
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        if status_filter and status_filter != "received":
            try:
                normalize_order_status(status_filter)
            except ValueError as ex:
                return jsonify(error=str(ex)), 400
        orders = get_seller_orders(
            connection,
            user.Id,
            status_filter or None,
        )
        return jsonify(orders=orders)


@app.post("/api/products/mine/orders/<order_id>/accept")
def accept_seller_order(order_id):
    data = request.get_json(silent=True) or {}
    try:
        custom_note = parse_tracking_note(data.get("note"))
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        if not seller_owns_order(connection, order_id, user.Id):
            return jsonify(error="Order not found."), 404
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        if current_status != "pending":
            return jsonify(error="This order has already been accepted."), 409
        record_order_status_event(
            connection,
            order_id,
            "confirmed",
            custom_note or f"Seller confirmed the order. Updated by {user.Name}.",
            tracking_location_for("confirmed", row.DeliveryAddress),
            user.Id,
            actor_role="seller",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        payload = build_tracking_payload(connection, updated)
        enrich_seller_order_flags(payload, updated)
        return jsonify(order=payload)


@app.post("/api/products/mine/orders/<order_id>/payment-accepted")
def accept_seller_order_payment(order_id):
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        if not seller_owns_order(connection, order_id, user.Id):
            return jsonify(error="Order not found."), 404
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        payment_status = normalize_payment_status(
            getattr(row, "PaymentStatus", None) or "pending"
        )
        if payment_status == "paid":
            return jsonify(error="Payment has already been accepted."), 409
        if payment_status not in {"pending", "failed"}:
            return jsonify(error="This payment cannot be marked as accepted."), 409
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        connection.execute(
            """
            UPDATE dbo.Orders
            SET PaymentStatus = 'paid', UpdatedAt = ?
            WHERE Id = ?
            """,
            now,
            order_id,
        )
        record_order_status_event(
            connection,
            order_id,
            row.Status,
            f"Payment accepted by {user.Name}.",
            tracking_location_for(
                normalize_order_status(row.Status), row.DeliveryAddress
            ),
            user.Id,
            actor_role="seller",
            event_type="payment",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        return jsonify(order=build_tracking_payload(connection, updated))


@app.post("/api/products/mine/orders/<order_id>/advance")
def advance_seller_order(order_id):
    data = request.get_json(silent=True) or {}
    try:
        custom_note = parse_tracking_note(data.get("note"))
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        if not seller_owns_order(connection, order_id, user.Id):
            return jsonify(error="Order not found."), 404
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        next_status = seller_next_status(current_status)
        if not next_status:
            return jsonify(error="This order cannot be advanced further."), 409
        if not can_transition_status(current_status, next_status):
            return jsonify(error="Invalid order status change."), 409
        note = custom_note or {
            "preparing": f"Bouquet preparation started. Updated by {user.Name}.",
            "out_for_delivery": f"Order is out for delivery. Updated by {user.Name}.",
            "delivered": f"Order marked delivered by {user.Name}.",
        }.get(next_status, f"Order updated by {user.Name}.")
        record_order_status_event(
            connection,
            order_id,
            next_status,
            note,
            tracking_location_for(next_status, row.DeliveryAddress),
            user.Id,
            actor_role="seller",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        payload = build_tracking_payload(connection, updated)
        enrich_seller_order_flags(payload, updated)
        return jsonify(order=payload)


@app.post("/api/products/mine/orders/<order_id>/notes")
def seller_order_note(order_id):
    data = request.get_json(silent=True) or {}
    try:
        note = parse_tracking_note(data.get("note"))
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    if not note:
        return jsonify(error="Enter an update for the buyer."), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        if not seller_owns_order(connection, order_id, user.Id):
            return jsonify(error="Order not found."), 404
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        if current_status in {"cancelled", "refunded"}:
            return jsonify(error="This order can no longer be updated."), 409
        record_order_status_event(
            connection,
            order_id,
            current_status,
            note,
            tracking_location_for(current_status, row.DeliveryAddress),
            user.Id,
            actor_role="seller",
            event_type="note",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        payload = build_tracking_payload(connection, updated)
        enrich_seller_order_flags(payload, updated)
        return jsonify(order=payload)


@app.post("/api/upload")
def upload_image():
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error

    if "image" not in request.files:
        return jsonify(error="Choose an image file from your computer."), 400
    file = request.files["image"]
    if not file:
        return jsonify(error="Choose an image file from your computer."), 400

    extension = image_extension(file)
    if not extension:
        return jsonify(error="Only JPG, PNG, WEBP, or GIF images are allowed."), 400

    data = file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify(error="Image must be 5 MB or smaller."), 400
    if not data:
        return jsonify(error="The selected image file is empty."), 400

    folder = uploads_dir()
    filename = f"{uuid.uuid4().hex}{extension}"
    (folder / filename).write_bytes(data)
    return jsonify(url=f"/uploads/{filename}"), 201


def product_fields(data):
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    image = str(data.get("image", "")).strip()
    description = str(data.get("description", "")).strip()
    try:
        price = round(float(data.get("price", 0)), 2)
    except (TypeError, ValueError):
        price = 0
    if not name or not category or not image or not description or price <= 0:
        return None
    return name, price, category, image, description


@app.post("/api/products")
def create_product():
    fields = product_fields(request.get_json(silent=True) or {})
    if not fields:
        return jsonify(error="Complete all fields and enter a valid price."), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        product_id = "p_" + uuid.uuid4().hex[:12]
        connection.execute(
            """
            INSERT INTO dbo.Products
                (Id, Name, Price, Category, Image, Description, CreatedByUserId)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            product_id, *fields, user.Id,
        )
        connection.commit()
        row = owned_product(connection, product_id, user.Id)
        return jsonify(product=product_json(row, user.Id)), 201


@app.put("/api/products/<product_id>")
def update_product(product_id):
    fields = product_fields(request.get_json(silent=True) or {})
    if not fields:
        return jsonify(error="Complete all fields and enter a valid price."), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        existing = owned_product(connection, product_id, user.Id)
        if not existing:
            return jsonify(error="You can only update bouquets you created."), 403
        connection.execute(
            """
            UPDATE dbo.Products
            SET Name = ?, Price = ?, Category = ?, Image = ?, Description = ?
            WHERE Id = ? AND CreatedByUserId = ?
            """,
            *fields, product_id, user.Id,
        )
        connection.commit()
        row = owned_product(connection, product_id, user.Id)
        return jsonify(product=product_json(row, user.Id))


@app.delete("/api/products/<product_id>")
def delete_product(product_id):
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        existing = owned_product(connection, product_id, user.Id)
        if not existing:
            return jsonify(error="You can only delete bouquets you created."), 403
        connection.execute(
            "DELETE FROM dbo.CartItems WHERE ProductId = ?", product_id
        )
        connection.execute(
            "DELETE FROM dbo.Products WHERE Id = ? AND CreatedByUserId = ?",
            product_id, user.Id,
        )
        connection.commit()
        return jsonify(ok=True)


def get_cart(connection, user_id):
    rows = connection.execute(
        """
        SELECT p.Id, p.Name, p.Price, p.Category, p.Image, p.Description,
               p.CreatedByUserId, c.Quantity
        FROM dbo.CartItems c
        JOIN dbo.Products p ON p.Id = c.ProductId
        WHERE c.UserId = ?
        """,
        user_id,
    ).fetchall()
    items = [
        {**product_json(row, user_id), "qty": row.Quantity}
        for row in rows
    ]
    return items, round(sum(item["price"] * item["qty"] for item in items), 2)


def search_products(connection, query, max_price=None):
    sql = "SELECT Id, Name, Price, Category, Image, Description, CreatedByUserId FROM dbo.Products WHERE 1=1"
    params = []
    if query:
        sql += " AND (LOWER(Name) LIKE ? OR LOWER(Description) LIKE ? OR LOWER(Category) LIKE ?)"
        pattern = f"%{query.lower()}%"
        params.extend([pattern, pattern, pattern])
    if max_price is not None:
        sql += " AND Price <= ?"
        params.append(max_price)
    sql += " ORDER BY Price ASC, Name"
    rows = connection.execute(sql, *params).fetchall()
    return [product_json(row) for row in rows]


@app.post("/api/ai/chat")
def ai_chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return jsonify(error="messages must be a non-empty list."), 400

    allowed_tools = {tool["name"] for tool in AI_TOOL_DEFINITIONS}
    cart_mutating_tools = {"add_to_cart", "remove_from_cart", "update_quantity", "create_order"}
    cart_updated = False
    with db_connection() as connection:
        user = current_user(connection)

        def tool_runner(name, args):
            nonlocal cart_updated
            normalized = normalize_tool_name(name)
            if normalized not in allowed_tools:
                return {"error": f"Unsupported tool: {name}"}
            if normalized in USER_REQUIRED_TOOLS and not user:
                return {"error": "Please log in to use this feature."}
            try:
                result = execute_ai_tool(connection, normalized, args or {}, user)
                if normalized in cart_mutating_tools and (
                    result.get("ok")
                    or result.get("orderId")
                ):
                    cart_updated = True
                return result
            except Exception:
                app.logger.exception("AI tool failed: %s", normalized)
                return {"error": "Something went wrong while fetching store data."}

        chat_messages = list(messages)
        if not chat_messages or chat_messages[0].get("role") != "system":
            chat_messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}] + chat_messages
        try:
            response = gemini_agent_chat(chat_messages, tool_runner)
            connection.commit()
        except Exception as ex:
            connection.rollback()
            app.logger.exception("AI chat failed")
            return jsonify(error=f"AI chat failed: {type(ex).__name__}: {ex}"), 500

    return jsonify(
        content=response.get("content", ""),
        cartUpdated=cart_updated,
        function_call=None,
        arguments=None,
    )

def apply_coupon_to_total(code, total):
    normalized = str(code or "").strip().lower()
    if normalized == "spring10":
        return {"code": "SPRING10", "discount": round(total * 0.10, 2), "description": "10% off your order."}
    if normalized == "welcome15":
        return {"code": "WELCOME15", "discount": round(min(total, 150) * 0.15, 2), "description": "15% discount up to ₹150."}
    return None


def get_delivery_windows(start_date):
    slots = []
    for day_offset in range(0, 7):
        day = start_date + timedelta(days=day_offset)
        for hour in (9, 11, 13, 15, 17, 19):
            slots.append({"slot": day.strftime("%Y-%m-%dT") + f"{hour:02}:00"})
    return slots


def get_product_by_id(connection, product_id, viewer_id=None):
    row = connection.execute(
        "SELECT Id, Name, Price, Category, Image, Description, CreatedByUserId, StockQuantity, IsGiftItem, OccasionTags FROM dbo.Products WHERE Id = ?",
        product_id,
    ).fetchone()
    return product_json(row, viewer_id) if row else None


def get_customer_addresses(connection, user_id):
    rows = connection.execute(
        "SELECT Id, Label, Recipient, Line1, City, State, PostalCode, Country, Phone FROM dbo.Addresses WHERE UserId = ? ORDER BY CreatedAt DESC",
        user_id,
    ).fetchall()
    return [address_json(row) for row in rows]


def add_address(connection, user_id, address):
    address_id = "a_" + uuid.uuid4().hex[:16]
    connection.execute(
        "INSERT INTO dbo.Addresses (Id, UserId, Label, Recipient, Line1, City, State, PostalCode, Country, Phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        address_id,
        user_id,
        address.get("label", "Home"),
        address.get("recipient", "Recipient"),
        address.get("line1", ""),
        address.get("city", ""),
        address.get("state", ""),
        address.get("postalCode", ""),
        address.get("country", ""),
        address.get("phone", ""),
    )
    return address_json(connection.execute(
        "SELECT Id, Label, Recipient, Line1, City, State, PostalCode, Country, Phone FROM dbo.Addresses WHERE Id = ?",
        address_id,
    ).fetchone())


def execute_ai_tool(connection, name, args, user):
    if name == "search_flowers":
        occasion = str(args.get("occasion", "") or "").strip()
        budget = args.get("budget")
        keywords = str(args.get("keywords", "") or "").strip()
        count = int(args.get("count", 5))
        query = " ".join([occasion, keywords]).strip()
        products = search_products(connection, query, budget)
        return {"results": products[:count]}

    if name == "get_flower_details":
        product_id = resolve_product_reference(
            connection, args.get("productId") or args.get("productName")
        )
        if not product_id:
            return {"error": "Product not found."}
        viewer_id = user.Id if user else None
        product = get_product_by_id(connection, product_id, viewer_id)
        return {"product": product} if product else {"error": "Product not found."}

    if name == "recommend_flowers":
        occasion = str(args.get("occasion", "") or "").strip()
        budget = args.get("budget")
        products = search_products(connection, occasion, budget)
        return {"recommendations": products[:6]}

    if name == "add_to_cart":
        product_id = resolve_product_reference(
            connection, args.get("productId") or args.get("productName") or args.get("name")
        )
        quantity = max(1, int(args.get("quantity", args.get("qty", 1))))
        if not product_id:
            return {"error": "Product not found."}
        purchasable, purchase_error = is_purchasable_product(
            connection, product_id, user.Id
        )
        if not purchasable:
            return {"error": purchase_error}
        upsert_cart_item(connection, user.Id, product_id, quantity)
        items, total = get_cart(connection, user.Id)
        return {"ok": True, "productId": product_id, "items": items, "total": total}

    if name == "remove_from_cart":
        product_id = resolve_product_reference(
            connection, args.get("productId") or args.get("productName") or args.get("name")
        )
        if not product_id:
            return {"error": "Product not found in cart."}
        connection.execute(
            "DELETE FROM dbo.CartItems WHERE UserId = ? AND ProductId = ?",
            user.Id, product_id,
        )
        items, total = get_cart(connection, user.Id)
        return {"ok": True, "productId": product_id, "items": items, "total": total}

    if name == "update_quantity":
        product_id = resolve_product_reference(
            connection, args.get("productId") or args.get("productName") or args.get("name")
        )
        quantity = max(1, int(args.get("quantity", args.get("qty", 1))))
        if not product_id:
            return {"error": "Product not found in cart."}
        connection.execute(
            "UPDATE dbo.CartItems SET Quantity = ? WHERE UserId = ? AND ProductId = ?",
            quantity, user.Id, product_id,
        )
        items, total = get_cart(connection, user.Id)
        return {"ok": True, "productId": product_id, "items": items, "total": total}

    if name == "view_cart":
        items, total = get_cart(connection, user.Id)
        return {"items": items, "total": total}

    if name == "apply_coupon":
        code = str(args.get("couponCode", "") or "").strip()
        items, total = get_cart(connection, user.Id)
        coupon = apply_coupon_to_total(code, total)
        if not coupon:
            return {"error": "Coupon not recognized."}
        return {"coupon": coupon, "totalBefore": total, "totalAfter": round(total - coupon["discount"], 2)}

    if name == "estimate_delivery":
        requested = str(args.get("requestedDate", "") or "").strip()
        try:
            requested_date = datetime.fromisoformat(requested)
        except ValueError:
            return {"error": "Invalid delivery date."}
        if requested_date < datetime.now(timezone.utc):
            return {"error": "Delivery date must be in the future."}
        if requested_date.hour < 9 or requested_date.hour > 19:
            return {"available": False, "message": "Available delivery hours are 09:00 to 19:00."}
        return {"available": True, "scheduled": requested_date.isoformat()}

    if name == "get_delivery_slots":
        request_date = datetime.utcnow().date()
        return {"slots": get_delivery_windows(request_date)}

    if name == "create_order":
        delivery_address, address_error = validate_delivery_address(
            args.get("deliveryAddress")
        )
        if address_error:
            return {"error": address_error}
        delivery_date = args.get("deliveryDate")
        payment_method = normalize_payment_method(
            str(args.get("paymentMethod", "") or "").strip() or None
        )
        try:
            delivery_date_value = datetime.fromisoformat(delivery_date) if delivery_date else None
        except Exception:
            return {"error": "Invalid delivery date format."}
        items, total = get_cart(connection, user.Id)
        if not items:
            return {"error": "Your cart is empty."}
        valid_cart, cart_error = validate_cart_for_checkout(connection, user.Id, items)
        if not valid_cart:
            return {"error": cart_error}
        order_id, tracking_number = create_order_record(
            connection,
            user.Id,
            items,
            total,
            delivery_address,
            delivery_date_value,
            payment_method=payment_method,
            payment_status=checkout_payment_status(payment_method),
        )
        connection.execute("DELETE FROM dbo.CartItems WHERE UserId = ?", user.Id)
        return {
            "orderId": order_id,
            "trackingNumber": tracking_number,
            "status": "confirmed",
            "total": total,
        }

    if name == "track_order":
        order_id = str(args.get("orderId", "") or "").strip()
        tracking_number = str(args.get("trackingNumber", "") or "").strip()
        row = None
        if order_id:
            row = fetch_order_row(connection, order_id)
            if row and row.UserId != user.Id:
                row = None
        elif tracking_number:
            row = fetch_order_by_tracking(connection, tracking_number)
            if row and row.UserId != user.Id:
                row = None
        if not row:
            return {"error": "Order not found."}
        return {"order": build_tracking_payload(connection, row)}

    if name == "get_order_history":
        orders = []
        order_rows = connection.execute(
            f"""
            {ORDER_SELECT_SQL}
            WHERE o.UserId = ?
            ORDER BY o.CreatedAt DESC
            """,
            user.Id,
        ).fetchall()
        for order in order_rows:
            orders.append(build_tracking_payload(connection, order))
        return {"orders": orders}

    if name == "cancel_order":
        order_id = str(args.get("orderId", "") or "").strip()
        row = fetch_order_row(connection, order_id)
        if not row or row.UserId != user.Id:
            return {"error": "Order not found."}
        current_status = normalize_order_status(row.Status)
        if current_status not in CANCELLABLE_STATUSES:
            return {"error": "This order can no longer be cancelled."}
        record_order_status_event(
            connection,
            order_id,
            "cancelled",
            "Order cancelled by the buyer.",
            tracking_location_for("cancelled", row.DeliveryAddress),
            user.Id,
            actor_role="buyer",
        )
        return {"ok": True, "status": "cancelled"}

    if name == "search_gift_items":
        rows = connection.execute("SELECT Id, Name, Price, Category, Image, Description, CreatedByUserId, StockQuantity, IsGiftItem, OccasionTags FROM dbo.Products WHERE IsGiftItem = 1 ORDER BY Name").fetchall()
        return {"results": [product_json(row, user.Id if user else None) for row in rows]}

    if name == "suggest_greeting_card":
        occasion = str(args.get("occasion", "") or "").strip().lower()
        suggestions = [
            "With love and warm wishes on your special day.",
            "May your day bloom with joy and beauty.",
            "Sending heartfelt flowers and happiness your way.",
        ]
        if "birthday" in occasion:
            suggestions = [
                "Happy Birthday! May your day be as bright as these flowers.",
                "Wishing you a birthday filled with love and blossoms.",
            ]
        elif "anniversary" in occasion:
            suggestions = [
                "Happy Anniversary! Celebrating your love with flowers.",
                "To many more years of love and joy together.",
            ]
        return {"messages": suggestions}

    if name == "check_inventory":
        product_id = str(args.get("productId", "") or "").strip()
        row = connection.execute("SELECT StockQuantity FROM dbo.Products WHERE Id = ?", product_id).fetchone()
        return {"stockQuantity": int(row.StockQuantity) if row else 0} if row else {"error": "Product not found."}

    if name == "get_customer_addresses":
        return {"addresses": get_customer_addresses(connection, user.Id)}

    if name == "save_new_address":
        address = args.get("address") or {}
        saved = add_address(connection, user.Id, address)
        return {"address": saved}

    return {"error": f"Tool {name} is not implemented."}


def resolve_product_reference(connection, product_ref):
    ref = str(product_ref or "").strip()
    if not ref:
        return None
    row = connection.execute(
        "SELECT Id FROM dbo.Products WHERE Id = ?",
        ref,
    ).fetchone()
    if row:
        return row.Id
    row = connection.execute(
        """
        SELECT TOP 1 Id FROM dbo.Products
        WHERE LOWER(Name) = LOWER(?)
        ORDER BY Name
        """,
        ref,
    ).fetchone()
    if row:
        return row.Id
    pattern = f"%{ref.lower()}%"
    row = connection.execute(
        """
        SELECT TOP 1 Id FROM dbo.Products
        WHERE LOWER(Name) LIKE ?
        ORDER BY LEN(Name), Name
        """,
        pattern,
    ).fetchone()
    return row.Id if row else None


@app.get("/api/cart")
def cart():
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to view your cart."), 401
        items, total = get_cart(connection, user.Id)
        return jsonify(items=items, total=total)


@app.post("/api/cart/add")
def add_cart_item():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("productId", ""))
    try:
        quantity = max(1, int(data.get("qty", 1)))
    except (TypeError, ValueError):
        quantity = 1

    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to add items to your cart."), 401
        if not connection.execute(
            "SELECT 1 FROM dbo.Products WHERE Id = ?", product_id
        ).fetchone():
            return jsonify(error="Product not found."), 404
        purchasable, purchase_error = is_purchasable_product(
            connection, product_id, user.Id
        )
        if not purchasable:
            return jsonify(error=purchase_error), 400
        upsert_cart_item(connection, user.Id, product_id, quantity)
        connection.commit()
        return jsonify(ok=True)


@app.post("/api/cart/update")
def update_cart_item():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("productId", ""))
    try:
        quantity = max(1, int(data.get("qty", 1)))
    except (TypeError, ValueError):
        quantity = 1
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to modify your cart."), 401
        connection.execute(
            """
            UPDATE dbo.CartItems SET Quantity = ?
            WHERE UserId = ? AND ProductId = ?
            """,
            quantity, user.Id, product_id,
        )
        connection.commit()
        return jsonify(ok=True)


@app.post("/api/cart/remove")
def remove_cart_item():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("productId", ""))
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to modify your cart."), 401
        connection.execute(
            "DELETE FROM dbo.CartItems WHERE UserId = ? AND ProductId = ?",
            user.Id, product_id,
        )
        connection.commit()
        return jsonify(ok=True)


@app.post("/api/checkout")
def checkout():
    data = request.get_json(silent=True) or {}
    delivery_address, address_error = validate_delivery_address(data.get("address"))
    if address_error:
        return jsonify(error=address_error), 400
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to check out."), 401
        items, total = get_cart(connection, user.Id)
        if not items:
            return jsonify(error="Your cart is empty."), 400
        valid_cart, cart_error = validate_cart_for_checkout(connection, user.Id, items)
        if not valid_cart:
            return jsonify(error=cart_error), 400
        payment_method = normalize_payment_method(data.get("paymentMethod"))

        try:
            order_id, tracking_number = create_order_record(
                connection,
                user.Id,
                items,
                total,
                delivery_address,
                payment_method=payment_method,
                payment_status=checkout_payment_status(payment_method),
            )
            connection.execute("DELETE FROM dbo.CartItems WHERE UserId = ?", user.Id)
            connection.commit()
        except Exception:
            connection.rollback()
            app.logger.exception("Checkout failed")
            return jsonify(error="Could not place your order. Please try again."), 500

        order_row = fetch_order_row(connection, order_id)
        return jsonify(order=build_tracking_payload(connection, order_row)), 201


@app.get("/api/orders")
def orders():
    with db_connection() as connection:
        user = current_user(connection)
        if not user:
            return jsonify(error="Please log in to view your orders."), 401
        order_rows = connection.execute(
            f"""
            {ORDER_SELECT_SQL}
            WHERE o.UserId = ?
            ORDER BY o.CreatedAt DESC
            """,
            user.Id,
        ).fetchall()
        result = [
            build_tracking_payload(connection, order)
            for order in order_rows
        ]
        return jsonify(orders=result)


@app.get("/api/orders/<order_id>/tracking")
def order_tracking(order_id):
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        if row.UserId != user.Id and not seller_owns_order(connection, order_id, user.Id):
            return jsonify(error="Order not found."), 404
        payload = build_tracking_payload(connection, row)
        if seller_owns_order(connection, order_id, user.Id):
            enrich_seller_order_flags(payload, row)
        return jsonify(order=payload)


@app.post("/api/orders/<order_id>/notes")
def buyer_order_note(order_id):
    data = request.get_json(silent=True) or {}
    try:
        note = parse_tracking_note(data.get("note"))
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    if not note:
        return jsonify(error="Enter a message for the seller."), 400
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        row = fetch_order_row(connection, order_id)
        if not row or row.UserId != user.Id:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        if current_status in {"cancelled", "refunded"}:
            return jsonify(error="This order can no longer be updated."), 409
        record_order_status_event(
            connection,
            order_id,
            current_status,
            note,
            tracking_location_for(current_status, row.DeliveryAddress),
            user.Id,
            actor_role="buyer",
            event_type="note",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        return jsonify(order=build_tracking_payload(connection, updated))


@app.post("/api/orders/<order_id>/cancel")
def cancel_order(order_id):
    with db_connection() as connection:
        user, error = require_user(connection)
        if error:
            return error
        row = fetch_order_row(connection, order_id)
        if not row or row.UserId != user.Id:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        if current_status not in CANCELLABLE_STATUSES:
            return jsonify(error="This order can no longer be cancelled."), 409
        record_order_status_event(
            connection,
            order_id,
            "cancelled",
            "Order cancelled by the buyer.",
            tracking_location_for("cancelled", row.DeliveryAddress),
            user.Id,
            actor_role="buyer",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        return jsonify(order=build_tracking_payload(connection, updated))


@app.post("/api/orders/track")
def public_order_tracking():
    data = request.get_json(silent=True) or {}
    tracking_number = str(data.get("trackingNumber", "") or "").strip()
    email = str(data.get("email", "") or "").strip().lower()
    if not tracking_number or not email:
        return jsonify(error="Tracking number and email are required."), 400
    with db_connection() as connection:
        row = fetch_order_by_tracking(connection, tracking_number)
        if not row or row.Email.strip().lower() != email:
            return jsonify(error="No order found for that tracking number and email."), 404
        return jsonify(order=build_tracking_payload(connection, row))


@app.get("/api/admin/orders")
def admin_orders():
    with db_connection() as connection:
        admin, error = require_admin(connection)
        if error:
            return error
        status_filter = str(request.args.get("status", "") or "").strip().lower()
        query = f"""
            {ORDER_SELECT_SQL}
        """
        params = []
        if status_filter:
            query += " WHERE o.Status = ?"
            params.append(status_filter)
        query += " ORDER BY o.CreatedAt DESC"
        order_rows = connection.execute(query, *params).fetchall()
        return jsonify(orders=[
            build_tracking_payload(connection, order)
            for order in order_rows
        ])


@app.patch("/api/admin/orders/<order_id>/status")
def admin_update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    next_status = str(data.get("status", "") or "").strip().lower()
    note = str(data.get("note", "") or "").strip()
    location = str(data.get("location", "") or "").strip()
    if not next_status:
        return jsonify(error="Status is required."), 400
    try:
        normalize_order_status(next_status)
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    with db_connection() as connection:
        admin, error = require_admin(connection)
        if error:
            return error
        row = fetch_order_row(connection, order_id)
        if not row:
            return jsonify(error="Order not found."), 404
        current_status = normalize_order_status(row.Status)
        if not can_transition_status(current_status, next_status):
            return jsonify(
                error=f"Cannot change status from {current_status} to {next_status}."
            ), 409
        record_order_status_event(
            connection,
            order_id,
            next_status,
            note or ORDER_STATUSES.get(next_status, next_status.title()),
            tracking_location_for(next_status, row.DeliveryAddress, location),
            admin.Id,
            actor_role="admin",
        )
        connection.commit()
        updated = fetch_order_row(connection, order_id)
        return jsonify(order=build_tracking_payload(connection, updated))


@app.errorhandler(Exception)
def database_error(error):
    if isinstance(error, HTTPException):
        return error
    db_errors = (sqlite3.Error,)
    if pyodbc is not None:
        db_errors = (pyodbc.Error, sqlite3.Error)
    if not isinstance(error, db_errors):
        raise error
    app.logger.exception("Database error: %s", error)
    return jsonify(error="Database error. Please try again."), 500


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(uploads_dir(), filename)


@app.route("/<path:filename>")
def frontend_file(filename):
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    initialize_database()
    print(f"Database: {'SQLite ' + str(SQLITE_PATH) if using_sqlite() else SQL_SERVER + '\\\\' + SQL_DATABASE}")
    print(f"Admin login: {ADMIN_EMAIL}")
    print(f"AI_PROVIDER: {AI_PROVIDER}")
    print(f"AI_MODEL: {AI_MODEL}")
    print(f"AI_API_KEY prefix: {AI_API_KEY[:6]}...")
    if ADMIN_PASSWORD == "ChangeMe123!":
        print("WARNING: Change the default ADMIN_PASSWORD outside local development.")
    print(f"Petal & Stem running at http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
else:
    initialize_database()
