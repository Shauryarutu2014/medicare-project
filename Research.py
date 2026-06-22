import psycopg2

conn = psycopg2.connect(
    host="dpg-d8jq2kuk1jcs73e1rlk0-a.oregon-postgres.render.com",
    database="medicare_database",
    user="medicare_database_user",
    password="6ssEiOC01LoWdPrSnulD6Ko6vmHrWpaE",
    port="5432",
    sslmode="require"
)

print("Connected Successfully!")
conn.close()