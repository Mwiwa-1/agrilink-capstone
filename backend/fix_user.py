import sqlite3
import bcrypt

conn = sqlite3.connect('agrilink.db')
cursor = conn.cursor()


password = 'yusuf123'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


cursor.execute('''
    INSERT INTO users (full_name, phone, email, password_hash, role, farmer_type, is_active) 
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', ('Yusuf', '0770932885', 'yusuf@example.com', hashed, 'farmer', 'smallholder', 1))

conn.commit()
conn.close()

print("SUCCESS! User created cleanly.")
print("Email: yusuf@example.com")
print("Password: yusuf123")
