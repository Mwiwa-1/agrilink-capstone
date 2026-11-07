
#  AgriLink - Backend API

This is the official FastAPI backend for the **AgriLink** mobile application. It powers the marketplace, user authentication, advisory articles, and order management.



##  Prerequisites
Before you begin, make sure you have:
- **Python 3.10+** installed (Tested on Python 3.14).
- **Git** installed.



## How to Run the Backend (Step-by-Step)

### 1. Navigate to the backend folder
Open your terminal (or Command Prompt) and ensure you are in the `backend` directory:
```bash
cd backend
```

2. Create a Virtual Environment

This keeps the project's packages isolated from the rest of your computer.

```bash
python -m venv venv
```

3. Activate the Virtual Environment

· Windows:
  ```cmd
  venv\Scripts\activate
  ```
· Mac/Linux:
  ```bash
  source venv/bin/activate
  ```

(You will know it worked if you see (venv) at the start of your terminal line).

4. Install Dependencies

 Important Note for Python 3.14 Users: 
Because Python 3.14 is very new, the default SQLAlchemy installer fails. You must install this specific version first.

Run these commands one by one:

```bash
pip install sqlalchemy==2.1.6
```

```bash
pip install fastapi uvicorn python-jose bcrypt python-multipart email-validator
```

5. Set Up the Database (Optional)

To populate the database with sample products, listings, and advisory articles so you have data to test with, run:

```bash
python seed.py
```

6. Start the Server

Run the server with the host flag so it can accept connections from mobile phones on the same network:

```bash
uvicorn main:app --host 0.0.0.0 --reload
```

(Keep this terminal window open. The server must stay running for the app to work).

7. View API Documentation

Open your web browser and go to:
 http://127.0.0.1:8000/docs

This is the Swagger UI where you can test all endpoints directly from your browser.


 Test Accounts

Use these credentials to test the app:

Role Email Password
Farmer yusuf@example.com yusuf123
Buyer user@example.com buyer12345
Admin admin@example.com admin12345


Team Members

· Mwiwa Yusuf (Backend Lead)
· Nalule Aisha (Flutter Lead)
· Nakiranda Hafswah (Analyst & Integration)


