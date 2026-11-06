import sqlite3

conn = sqlite3.connect('agrilink.db')
cursor = conn.cursor()

cursor.execute("SELECT id, full_name, email, role FROM users")
users = cursor.fetchall()

print("\n---USERS IN DATABASE---")
for u in users:
    print(f"ID: {u[0] }) | Name: {u[1]} | Email: {u[2]} | Role: {u[3]}")

    print("----------------------\n")

    conn.close()