import json
import sqlite3

DB_PATH = "medicare.db"

# connect database
conn = sqlite3.connect(DB_PATH)

# cursor
cur = conn.cursor()

# create table if not exists
cur.execute("""
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem TEXT,
    symptoms TEXT,
    suggestions TEXT
)
""")

# open json file
with open("medicines.json", "r") as file:
    data = json.load(file)

# insert into database
for item in data:

    problem = item["problem"]

    symptoms = ", ".join(item["symptoms"])

    suggestions = ", ".join(item["suggestions"])

    cur.execute(
        """
        INSERT INTO medicines (problem, symptoms, suggestions)
        VALUES (?, ?, ?)
        """,
        (problem, symptoms, suggestions)
    )

# save changes
conn.commit()

# close
cur.close()
conn.close()

print("Data inserted successfully!")