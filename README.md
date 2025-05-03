
# ICICI Banking System (SQLite + Flask Framework)

A complete command-line banking application that allows users to create accounts, login securely, perform deposits, withdrawals, wire transfers, and view transaction history. Each transaction is logged securely per user. Sensitive information like PIN and SSN are encrypted.

---

## Features

- **Account Creation**
  - Auto-generated account numbers starting from 10001.
  - Collects first name, last name, email, phone number, and social security number.
  - PIN and SSN are hashed using SHA-256 for security.

- **Secure Login**
  - Account number + PIN based authentication.
  - PIN entered is hashed before verification.
  - 3 attempts allowed. After 3 failed attempts, account is locked for 1 minute.

- **Banking Operations**
  - Check current balance.
  - Deposit funds.
  - Withdraw funds (with retry system and lock after insufficient funds attempts).
  - **Wire Transfers**: Send money to another user's account if sufficient balance is available.

- **Transaction Logging**
  - Every deposit, withdrawal, and wire transfer is logged to a personal transaction file inside the `logs/` folder.
  - Transaction logs include timestamps.

- **Transaction History**
  - Users can view their transaction history directly from the menu.

- **Error Handling**
  - User-friendly error messages.
  - Handles wrong inputs, database errors, and file errors gracefully.

- **Database**
  - SQLite database (`banking.db`) is used.
  - `accounts` table stores user information securely.

---

## Table Structure (accounts)

| Column         | Type    | Description                        |
|----------------|---------|------------------------------------|
| account_number | INTEGER | Unique, auto-increment primary key |
| pin            | TEXT    | Encrypted PIN                     |
| balance        | REAL    | User balance (default 0.0)         |
| first_name     | TEXT    | First Name                        |
| last_name      | TEXT    | Last Name                         |
| email          | TEXT    | Email Address                     |
| phone          | TEXT    | Phone Number                      |
| ssn            | TEXT    | Encrypted Social Security Number  |

---

## Technologies Used

- Python 3
- SQLite (sqlite3 library)
- SHA-256 encryption (hashlib)
- Command-line Interface

---

## How to Run

1. Clone/download the project.
2. Make sure you have Python installed (version 3.x).
3. Run the file:

```bash
python main.py
```

4. Follow on-screen options to:
   - Create new accounts.
   - Login into accounts.
   - Perform banking operations.


---

## Future Improvements (optional)

- Add admin portal for account management.
- Add email and phone validation.
- Upgrade PIN hashing to bcrypt for even better security.
- Enable fund transfer between accounts.
- Add graphical user interface (GUI) using Tkinter or Flask.

---

## Author

Created with passion and security in mind.

---

## License

This project is for educational purposes and personal development. Feel free to use, improve, and extend it!
