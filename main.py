from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session

DATABASE = 'banking.db'

def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        account_number INTEGER PRIMARY KEY,
        pin TEXT NOT NULL,
        balance REAL DEFAULT 0.0,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        ssn TEXT NOT NULL
    );
    ''')
    conn.commit()
    return conn

# Home
@app.route('/')
def home():
    return render_template('home.html')

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        pin = request.form['pin']
        ssn = request.form['ssn']

        hashed_pin = hash_value(pin)
        hashed_ssn = hash_value(ssn)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(account_number) FROM accounts")
        result = cursor.fetchone()
        acc_num = (result['MAX(account_number)'] or 10000) + 1

        cursor.execute('''
            INSERT INTO accounts (account_number, pin, balance, first_name, last_name, email, phone, ssn)
            VALUES (?, ?, 0.0, ?, ?, ?, ?, ?)
        ''', (acc_num, hashed_pin, first_name, last_name, email, phone, hashed_ssn))
        conn.commit()
        conn.close()

        flash(f'Account created! Your Account Number: {acc_num}', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        acc_num = request.form['account_number']
        pin = request.form['pin']
        hashed_pin = hash_value(pin)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE account_number=? AND pin=?", (acc_num, hashed_pin))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['account_number'] = acc_num
            flash('Login Successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')

    return render_template('login.html')

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'account_number' not in session:
        return redirect(url_for('login'))
    account_number = session['account_number']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (account_number,))
    balance = cursor.fetchone()['balance']
    conn.close()
    return render_template('dashboard.html', balance=balance)

# Deposit
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = float(request.form['amount'])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?", (amount, session['account_number']))
        conn.commit()

        log_transaction(session['account_number'], f"Deposited ${amount:.2f}")
        conn.close()

        flash(f'${amount:.2f} deposited successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('deposit.html')

# Withdraw
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = float(request.form['amount'])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_number=?", (session['account_number'],))
        balance = cursor.fetchone()['balance']

        if amount > balance:
            flash('Insufficient funds.', 'danger')
        else:
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?", (amount, session['account_number']))
            conn.commit()

            log_transaction(session['account_number'], f"Withdrawn ${amount:.2f}")
            flash(f'${amount:.2f} withdrawn successfully.', 'success')

        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('withdraw.html')

# Wire Transfer
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        recipient = int(request.form['recipient'])
        amount = float(request.form['amount'])

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT balance FROM accounts WHERE account_number=?", (session['account_number'],))
        sender_balance = cursor.fetchone()['balance']

        cursor.execute("SELECT * FROM accounts WHERE account_number=?", (recipient,))
        receiver = cursor.fetchone()

        if not receiver:
            flash('Recipient account not found.', 'danger')
        elif amount > sender_balance:
            flash('Insufficient funds.', 'danger')
        else:
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?", (amount, session['account_number']))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?", (amount, recipient))
            conn.commit()

            log_transaction(session['account_number'], f"Transferred ${amount:.2f} to {recipient}")
            log_transaction(recipient, f"Received ${amount:.2f} from {session['account_number']}")

            flash(f'${amount:.2f} transferred to account {recipient}!', 'success')

        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('transfer.html')

# Transactions History
@app.route('/transactions')
def transactions():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    account_number = session['account_number']
    log_filename = f'logs/{account_number}_transactions.txt'

    logs = []
    if os.path.exists(log_filename):
        with open(log_filename, 'r') as file:
            logs = file.readlines()

    return render_template('transactions.html', logs=logs)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

# Transaction Logger
def log_transaction(account_number, action):
    if not os.path.exists('logs'):
        os.makedirs('logs')
    log_filename = f'logs/{account_number}_transactions.txt'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_filename, 'a') as file:
        file.write(f"{now} - {action}\n")

if __name__ == '__main__':
    app.run(debug=True)
