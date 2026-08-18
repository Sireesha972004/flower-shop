# Petal & Stem — Flower Bouquet Shop

A ready-to-run flower shop:

- Frontend: plain HTML, CSS, and JavaScript
- Backend: Python and Flask
- Database: SQL Server LocalDB
- Auth: registration, login, hashed passwords, and database-backed sessions
- Store: products, cart, checkout, and order history

## Run the project

Requirements:

- Python 3.10+
- SQL Server LocalDB
- Microsoft ODBC Driver 17 for SQL Server

From PowerShell:

```powershell
cd backend
python -m pip install -r requirements.txt
python app.py
```

Open http://localhost:3001.

The first start automatically creates the `FlowerShopDB` database, its tables,
and six sample products on `(localdb)\Local`.

## Database configuration

The defaults can be changed with environment variables:

```powershell
$env:SQL_SERVER = "(localdb)\Local"
$env:SQL_DATABASE = "FlowerShopDB"
$env:SQL_DRIVER = "ODBC Driver 17 for SQL Server"
$env:PORT = "3001"
$env:ADMIN_EMAIL = "admin@petalandstem.local"
$env:ADMIN_PASSWORD = "ChangeMe123!"
python app.py
```

## Bouquet management

Any logged-in user can:

- create their own bouquets
- update only bouquets they created
- delete only bouquets they created
- view them under **My Bouquets**

Created bouquets also appear in the public Shop.

Admin login (optional):

- Email: `admin@petalandstem.local`
- Password: `ChangeMe123!`

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before the first run to use different
credentials. Change the default password outside local development.

The application creates these tables:

- `Users`
- `Products`
- `CartItems`
- `Orders`
- `OrderItems`
- `Sessions`

Passwords are stored as PBKDF2-SHA256 hashes with 310,000 iterations and a
unique random salt. Plain-text passwords are never stored.

## Project layout

```text
flower-shop/
├── backend/
│   ├── app.py
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

## API

- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`
- `GET /api/me`
- `GET /api/products`
- `GET /api/products/mine`
- `POST /api/upload`
- `POST /api/products`
- `PUT /api/products/{id}`
- `DELETE /api/products/{id}`
- `GET /api/cart`
- `POST /api/cart/add`
- `POST /api/cart/update`
- `POST /api/cart/remove`
- `POST /api/checkout`
- `GET /api/orders`
