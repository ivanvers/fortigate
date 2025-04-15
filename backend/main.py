# file: backend/main.py
import os
import time
import threading
import sqlite3
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, IPvAnyAddress

DB_PATH = os.getenv("DB_PATH", "/app_data/data.db")

app = FastAPI()

# Ensure table is created at startup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS ip_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        object_id TEXT NOT NULL
    )''')
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_PATH)


# Pydantic model for input validation
class IPEntry(BaseModel):
    ip: IPvAnyAddress
    object_id: str  # Azure AD Object ID


@app.post("/add")
def add_ip(entry: IPEntry):
    conn = get_db()
    cur = conn.cursor()
    # Check how many IPs user has
    cur.execute("SELECT COUNT(*) FROM ip_entries WHERE object_id=?", (entry.object_id,))
    count = cur.fetchone()[0]
    if count >= 2:
        conn.close()
        raise HTTPException(status_code=400, detail="Max 2 IPs per user allowed.")

    # Insert new IP
    cur.execute("INSERT INTO ip_entries (ip, object_id) VALUES (?, ?)",
                (str(entry.ip), entry.object_id))
    conn.commit()
    conn.close()
    return {"status": "added", "ip": str(entry.ip)}


@app.get("/list/{object_id}")
def list_user_ips(object_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT ip FROM ip_entries WHERE object_id=?", (object_id,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


@app.delete("/delete/{object_id}/{ip}")
def delete_ip(object_id: str, ip: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ip_entries WHERE object_id=? AND ip=?", (object_id, ip))
    changes = cur.rowcount
    conn.commit()
    conn.close()
    if changes == 0:
        raise HTTPException(status_code=404, detail="IP not found for this user.")
    return {"status": "deleted", "ip": ip}


def generate_ip_list():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT ip FROM ip_entries")
            rows = cur.fetchall()
            conn.close()

            with open("/app_data/ip.txt", "w") as f:
                for r in rows:
                    f.write(r[0] + "\\n")
        except Exception as e:
            print(f"Error generating ip.txt: {e}")

        time.sleep(300)  # 5 minutes


# Start background thread
threading.Thread(target=generate_ip_list, daemon=True).start()
