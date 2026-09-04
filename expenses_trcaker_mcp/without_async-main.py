from fastmcp import FastMCP
import psycopg
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Optional
from datetime import datetime


mcp = FastMCP(name="Expense tracker mcp")

categories_path = os.path.join(
    os.path.dirname(__file__),
    "categories.json"
)

database_url = os.getenv("neon_postgres_url")

print(database_url)


# --------------------------------------------------
# Normalize Date
# --------------------------------------------------

def normalize_date(date_str: str):

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                date_str,
                fmt
            ).strftime("%Y-%m-%d")

        except ValueError:
            pass

    raise ValueError(
        f"Invalid date format: {date_str}. "
        "Use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD."
    )


# --------------------------------------------------
# Initial DB
# --------------------------------------------------

def init_db():

    with psycopg.connect(database_url) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                amount INTEGER NOT NULL,
                date DATE NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
            """
        )


init_db()


# --------------------------------------------------
# Add Expense
# --------------------------------------------------

@mcp.tool
def add_expense(
    date: str,
    amount: int,
    category: str,
    subcategory: Optional[str] = None,
    note: Optional[str] = None
):
    """
    Add expense in database.
    """

    date = normalize_date(date)

    query = """
        INSERT INTO expenses
        (date, amount, category, subcategory, note)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        date,
        amount,
        category,
        subcategory,
        note
    )

    try:

        with psycopg.connect(database_url) as conn:

            cursor = conn.execute(
                query,
                params
            )

            row = cursor.fetchone()

            return {
                "success": True,
                "id": row[0]
            }

    except Exception as e:

        return {
            "success": False,
            "message": f"Database error: {str(e)}"
        }


# --------------------------------------------------
# Get Expenses
# --------------------------------------------------

@mcp.tool
def get_expenses_given_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exact_date: Optional[str] = None
):
    """
    List all expenses in the given date range.
    """

    query = """
        SELECT
            id,
            date,
            amount,
            category,
            subcategory,
            note
        FROM expenses
    """

    conditions = []
    params = []

    if start_date:

        start_date = normalize_date(start_date)

        conditions.append("date >= %s")
        params.append(start_date)

    if end_date:

        end_date = normalize_date(end_date)

        conditions.append("date <= %s")
        params.append(end_date)

    if exact_date:

        exact_date = normalize_date(exact_date)

        conditions.append("date = %s")
        params.append(exact_date)

    if conditions:

        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id ASC"

    try:

        with psycopg.connect(
            database_url,
            row_factory=dict_row
        ) as conn:

            cursor = conn.execute(
                query,
                params
            )

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "date": str(row["date"]),
                    "amount": row["amount"],
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "note": row["note"]
                }
                for row in rows
            ]

    except Exception as e:

        return {
            "status": "error",
            "message": f"Error listing expenses: {str(e)}"
        }


# --------------------------------------------------
# Summarize
# --------------------------------------------------

@mcp.tool
def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None
):
    """
    Summarize expenses in the given date range.
    Both dates are inclusive.
    """

    start_date = normalize_date(start_date)
    end_date = normalize_date(end_date)

    query = """
        SELECT
            category,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN %s AND %s
    """

    params = [
        start_date,
        end_date
    ]

    if category:

        query += " AND category = %s"
        params.append(category)

    query += """
        GROUP BY category
        ORDER BY total_amount ASC
    """

    try:

        with psycopg.connect(
            database_url,
            row_factory=dict_row
        ) as conn:

            cursor = conn.execute(
                query,
                params
            )

            rows = cursor.fetchall()

            return [
                {
                    "category": row["category"],
                    "total_amount": row["total_amount"]
                }
                for row in rows
            ]

    except Exception as e:

        return {
            "status": "error",
            "message": f"Error summarizing expenses: {str(e)}"
        }


# --------------------------------------------------
# Delete Expense
# --------------------------------------------------

@mcp.tool
def delete_expense(id: int):
    """
    Delete a particular expense.
    """

    query = """
        DELETE FROM expenses
        WHERE id = %s
        RETURNING id
    """

    try:

        with psycopg.connect(database_url) as conn:

            cursor = conn.execute(
                query,
                (id,)
            )

            deleted = cursor.fetchone()

            if deleted is None:

                return {
                    "success": False,
                    "message": "Expense not found",
                    "id": id
                }

            return {
                "success": True,
                "message": "Expense deleted",
                "id": deleted[0]
            }

    except Exception as e:

        return {
            "success": False,
            "message": f"Database error: {str(e)}"
        }


# --------------------------------------------------
# Categories Resource
# --------------------------------------------------

@mcp.resource(
    "expense:///categories",
    mime_type="application/json"
)
def categories():

    import json

    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:

        with open(
            categories_path,
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()

    except Exception:

        return json.dumps(
            default_categories,
            indent=2
        )


# --------------------------------------------------
# Run MCP Server
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run()