# app.py -- Simple FastAPI HR microservice (SQLite by default)
import os
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlalchemy
import databases
from dotenv import load_dotenv

# Load .env if present (optional)
load_dotenv()

# DATABASE_URL can be in .env, else fallback to local sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mdm_hr.db")

# Async DB (sqlite for quick start). For Postgres you can change DATABASE_URL accordingly.
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Employees table definition (SQLAlchemy)
employees = sqlalchemy.Table(
    "employee",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_no", sqlalchemy.String, unique=True, nullable=True),
    sqlalchemy.Column("first_name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("last_name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("email", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("phone", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("branch", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("job_title", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("salary", sqlalchemy.Numeric, nullable=True),
    sqlalchemy.Column("date_hired", sqlalchemy.Date, nullable=True),
)

# Create engine and tables (synchronous only for initial setup)
engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
metadata.create_all(engine)

# Pydantic models for request/response validation
class EmployeeIn(BaseModel):
    employee_no: Optional[str] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    branch: Optional[str] = None
    job_title: Optional[str] = None
    salary: Optional[float] = None
    date_hired: Optional[date] = None

class EmployeeOut(EmployeeIn):
    id: int

app = FastAPI(title="MDM HR API (FastAPI)", version="0.1")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Create employee
@app.post("/api/employees", response_model=EmployeeOut)
async def create_employee(emp: EmployeeIn):
    query = employees.insert().values(**emp.dict())
    emp_id = await database.execute(query)
    return {**emp.dict(), "id": emp_id}

# List employees (with optional branch filter)
@app.get("/api/employees", response_model=List[EmployeeOut])
async def list_employees(branch: Optional[str] = None, limit: int = 100):
    q = employees.select().limit(limit)
    if branch:
        q = q.where(employees.c.branch == branch)
    rows = await database.fetch_all(q)
    return [dict(r) for r in rows]

# Get single employee
@app.get("/api/employees/{emp_id}", response_model=EmployeeOut)
async def get_employee(emp_id: int):
    q = employees.select().where(employees.c.id == emp_id)
    row = await database.fetch_one(q)
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    return dict(row)

# Update employee
@app.put("/api/employees/{emp_id}", response_model=EmployeeOut)
async def update_employee(emp_id: int, emp: EmployeeIn):
    q = employees.update().where(employees.c.id == emp_id).values(**emp.dict())
    await database.execute(q)
    q2 = employees.select().where(employees.c.id == emp_id)
    row = await database.fetch_one(q2)
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found after update")
    return dict(row)

# Delete (soft-delete would be better in prod)
@app.delete("/api/employees/{emp_id}")
async def delete_employee(emp_id: int):
    q = employees.delete().where(employees.c.id == emp_id)
    res = await database.execute(q)
    return {"deleted_id": emp_id}
