import json
import psycopg2

DATABASE_URL = "postgresql://medicare_database_user:6ssEiOC01LoWdPrSnulD6Ko6vmHrWpaE@dpg-d8jq2kuk1jcs73e1rlk0-a.virginia-postgres.render.com/medicare_database"

# connect database
conn = psycopg2.connect(DATABASE_URL)

# cursor
cur = conn.cursor()

# create table if not exists
cur.execute("""
CREATE TABLE IF NOT EXISTS medicines (
    id SERIAL PRIMARY KEY,
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
        VALUES (%s, %s, %s)
        """,
        (problem, symptoms, suggestions)
    )

# save changes
conn.commit()

# close
cur.close()
conn.close()

print("Data inserted successfully!")

