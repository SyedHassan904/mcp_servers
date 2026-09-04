from fastmcp import FastMCP
import psycopg
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Optional
from datetime import datetime


mcp = FastMCP(name="Expense tracker mcp")

categories_path = os.path.join(os.path.dirname(__file__),"categories.json")


def get_database_url():
    database_url = os.getenv("NEON_POSTGRES_URL")

    if not database_url:
        raise RuntimeError("NEON_POSTGRES_URL is not configured")

    return database_url

# Normalize the date(user can give date in multiple ways so convert into one standart)
def normalize_date(date_str:str):
    formats =[
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d"
    ]
    
    for fmt in  formats:
        try:
            return datetime.strptime(date_str,fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    raise ValueError(
        f"Invalid date format: {date_str}. "
        "Use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD."
        )
    
    

# Initial DB
def init_db():
    
    with psycopg.connect(get_database_url()) as conn:
        conn.execute(
            """
            create table if not exists expenses(
            id integer generated always as identity primary key,
            amount integer not null,
            date DATE not null,
            category text not null,
            subcategory text default '',
            note text default ''
            )
            """
        )
        



# Add Expense tool

@mcp.tool
async def add_expense(date:str,amount:int,category:str,subcategory:Optional[str],note:Optional[str]):
    """
    it add expense in db
    """
    
    query = "insert into expenses (date,amount,category,subcategory,note) values (%s,%s,%s,%s,%s) returning id"
    
    params = (date,amount,category,subcategory,note)
    
    try:
        async with await psycopg.AsyncConnection.connect(get_database_url()) as conn:
            cursor = await conn.execute(query,params)
            row = await cursor.fetchone()
            return {"success":"Ok","id":row[0]}
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
        conditions.append("date>= %s")
        params.append(start_date)
    if end_date:
        end_date = normalize_date(end_date)
        conditions.append("date<= %s")
        params.append(end_date)
    if exact_date:
        exact_date=normalize_date(exact_date)
        conditions.append("date=%s")
        params.append(exact_date)
    if conditions:
        query+=" where " + " and ".join(conditions)
    query +=" order by id asc"    
    
    try:
        async with await psycopg.AsyncConnection.connect(get_database_url(),row_factory=dict_row) as conn:
            
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
    where date between %s and %s
    """
    start_date=normalize_date(start_date)
    end_date=normalize_date(end_date)
    params = [start_date,end_date]
    if category:
        query+=" and category=%s"
        params.append(category)
    
    query+=" group by category order by total_amount asc"
    
    try:
        async with await psycopg.AsyncConnection.connect(get_database_url(),row_factory=dict_row) as conn:
            
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
    query = "delete from expenses where id=%s"
    
    async with await psycopg.AsyncConnection.connect(get_database_url()) as conn:
        cur = await conn.execute(query,(id,))
        if cur.rowcount==0:
            return {"success":False,"message":"Expense not deleted","id":id}
        
        return {"success":True,"message":"Expense deleted","id":id}




@mcp.tool
async def edit_expense(id:int,date:Optional[str],amount:Optional[int],category:Optional[str],subcategory:Optional[str],note:Optional[str]):
    """
    Edit the existing expense
    """
    update_query = "update expenses set "
    params=[]
    conditions=[]
    async with await psycopg.AsyncConnection.connect(get_database_url(),row_factory=dict_row) as conn:
        try:
            cur = await conn.execute("select * from expenses where id=%s",(id,))
            row = await cur.fetchone()
            if row is None:
                return {"success": False,"message": "Expense not found","id": id}
            if date:
                row["date"]=normalize_date(date)
                conditions.append("date=%s")
                params.append(row["date"])
            if amount is not None:
                row["amount"]=amount
                conditions.append("amount=%s")
                params.append(row["amount"])
            if category:
                row["category"]=category
                conditions.append("category=%s")
                params.append(row["category"])
            if subcategory:
                row["subcategory"]=subcategory
                conditions.append("subcategory=%s")
                params.append(row["subcategory"])
            if note:
                row["note"]=note
                conditions.append("note=%s")
                params.append(row["note"])
            
            # Nothing to update
            if not conditions:
                return {"success": False,"message": "No fields provided to update","id": id}
            
            update_query=update_query+ ",".join(conditions) + " where id=%s returning id"
            params.append(id)
            cur = await conn.execute(update_query,params)
            row = await cur.fetchone()
            return {"success":"Ok","id":row[0]}
        except Exception as e:
            if "readonly" in str(e).lower():
                return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
            return {"status": "error", "message": f"Database error: {str(e)}"}
        


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
    init_db()
    mcp.run()
