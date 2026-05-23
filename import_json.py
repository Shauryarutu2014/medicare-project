import json
import psycopg2

# connect database
conn = psycopg2.connect(
    host="localhost",
    database="medicare_db",
    user="postgres",
    password="SNG@2014"
)

cur = conn.cursor()

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

conn.commit()

cur.close()
conn.close()

print("Data inserted successfully!")