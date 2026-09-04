from fastmcp import FastMCP
import os
from datetime import datetime
import aiosqlite
import sqlite3
from typing import Optional


mcp = FastMCP(name="Expenses Tracker MCP Server")

db_path = os.path.join(os.path.dirname(__file__),"expense.db")
categories_path = os.path.join(os.path.dirname(__file__),"categories.json")


def normalize_date(date_str):
    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    raise ValueError(
        f"Invalid date format: {date_str}. "
        "Use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD."
    )
    
    

def init_db():
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table if not exists expenses(
                id integer primary key autoincrement,
                date text not null,
                amount int not null,
                category text not null,
                subcategory text default '',
                note text default ''   
            )
            """       
        )
    
init_db()

@mcp.tool
async def add_expense(date:str,amount:int,category:str,subcategory:str,note:str):
    """
    It add the expenses in db.
    """
    date = normalize_date(date)
    
    try:
        query = "insert into expenses (date,amount,category,subcategory,note) values (?,?,?,?,?)"
        
        params = (date,amount,category,subcategory,note)
        
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(query,params)
            await conn.commit()
            return {"success":"ok","id":cursor.lastrowid}
        
    except Exception as e:
        if "readonly" in str(e).lower():
            return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
        return {"status": "error", "message": f"Database error: {str(e)}"}
    

@mcp.tool
async def get_expenses_given_range(start_date:Optional[str]=None,end_date:Optional[str]=None,exact_date:Optional[str]=None):
    """
    List all Expenses in the given range of date givem by user
    """

    query = "select id, date,amount,category,subcategory,note from expenses"
    conditions=[]
    params=[]
    if start_date:
        start_date= normalize_date(start_date)
        conditions.append("date>= ?")
        params.append(start_date)
    if end_date:
        end_date = normalize_date(end_date)
        conditions.append("date<= ?")
        params.append(end_date)
    if exact_date:
        exact_date=normalize_date(exact_date)
        conditions.append("date=?")
        params.append(exact_date)
    if conditions:
        query+=" where " + " and ".join(conditions)
    query +=" order by id asc"    
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query,params)
            return [
                {
                "id":row["id"],
                "date":row["date"],
                "amount":row["amount"],
                "category":row["category"],
                "subcategory":row["subcategory"],
                "note":row["note"]
                }
                for row in await cursor.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}
        
        
@mcp.tool
async def summarize(start_date:str,end_date:str,category:str=None):
    """
    summarize the expenses in given range given by user both date inclusive
    """
    query = """
    select category , sum(amount) as total_amount 
    from expenses
    where date between ? and ?
    """
    start_date=normalize_date(start_date)
    end_date=normalize_date(end_date)
    params = [start_date,end_date]
    if category:
        query+=" and category=?"
        params.append(category)
    
    query+=" group by category order by total_amount asc"
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query,params)
            return [{
                "category":row["category"],
                "total_amount":row["total_amount"]
            } for row in await cursor.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}
        

@mcp.tool
async def delete_expense(id:int):
    """
    delete the partivular expense
    """
    query = "delete from expenses where id=?"
    
    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute(query,(id,))
        if cur.rowcount==0:
            return {"success":False,"message":"Expense not deleted","id":id}
        await conn.commit()
        return {"success":True,"message":"Expense deleted","id":id}


@mcp.resource("expense:///categories",mime_type="application/json")
def categories():
    
    try:
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
            with open(categories_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            import json
            return json.dumps(default_categories, indent=2)
    except Exception as e:
        return f'{{"error": "Could not load categories: {str(e)}"}}'

if __name__=="__main__":
    mcp.run()
        
        
    

