from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
import os
import io
from datetime import datetime
import csv
import uuid
from dotenv import load_dotenv
import os
load_dotenv()
import boto3
from botocore.exceptions import BotoCoreError, ClientError
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
        notes = request.form.get('Cash', 'Cheque')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?",
                       (amount, session['account_number']))
        conn.commit()

        log_transaction(session['account_number'], "Deposited", amount, notes)
        conn.close()

        flash(f'₹{amount:.2f} deposited successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('deposit.html')


# Withdraw
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = float(request.form['amount'])
        notes = request.form.get('Cash', 'Cheque')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_number=?", (session['account_number'],))
        balance = cursor.fetchone()['balance']

        if amount > balance:
            flash('Insufficient funds.', 'danger')
        else:
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?",
                           (amount, session['account_number']))
            conn.commit()

            log_transaction(session['account_number'], "Withdrawn", amount, notes)
            flash(f'₹{amount:.2f} withdrawn successfully.', 'success')

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
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?",
                           (amount, session['account_number']))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?", (amount, recipient))
            conn.commit()

            log_transaction(session['account_number'], "Wire", amount, f"to {recipient}")
            log_transaction(recipient, "Wire", amount, f"from {session['account_number']}")

            flash(f'₹{amount:.2f} transferred to account {recipient}!', 'success')

        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('transfer.html')


# Transactions History
@app.route('/transactions')
def transactions():
    if 'account_number' not in session:
        return redirect(url_for('login'))

    account_number = session['account_number']
    filename = f'{account_number}_transactions.csv'
    s3_folder = os.getenv('S3_FOLDER')
    s3_key = f'{s3_folder}/{filename}' if s3_folder else filename
    bucket_name = os.getenv('S3_BUCKET_NAME')

    logs = []

    # Initialize S3 client
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )

    # Fetch CSV from S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        body = response['Body'].read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(body))
        logs = list(reader)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logs = []
        else:
            logs = []
            app.logger.error(f"[ERROR] Unable to fetch transactions: {e}")
    except BotoCoreError as e:
        logs = []
        app.logger.error(f"[ERROR] BotoCore error: {e}")
    except Exception as e:
        logs = []
        app.logger.error(f"[ERROR] Unexpected error reading transactions: {e}")

    # Pagination setup
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    per_page = 10
    total = len(logs)
    total_pages = (total + per_page - 1) // per_page
    if page > total_pages and total_pages > 0:
        return redirect(url_for('transactions', page=total_pages))

    start = (page - 1) * per_page
    end = start + per_page
    logs = logs[start:end]

    # Grouped pagination logic
    group_size = 3
    group_index = (page - 1) // group_size
    start_page = group_index * group_size + 1
    end_page = min(start_page + group_size - 1, total_pages)
    has_next_group = end_page < total_pages
    has_prev_group = start_page > 1

    return render_template(
        'transactions.html',
        logs=logs,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        has_next_group=has_next_group,
        has_prev_group=has_prev_group
    )



# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))


# Transaction Logger


def log_transaction(account_number, trnsc_type, amount, notes):
    # Load S3 configurations from environment variables
    bucket_name = os.getenv('S3_BUCKET_NAME')
    s3_folder = os.getenv('S3_FOLDER')
    filename = f'{account_number}_transactions.csv'
    s3_key = f'{s3_folder}/{filename}'

    trnsc_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trnsc_id = str(uuid.uuid4())

    # Initialize S3 client with AWS credentials from environment variables
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )

    # Try to fetch existing CSV from S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        body = response['Body'].read().decode('utf-8')
        csv_lines = list(csv.reader(io.StringIO(body)))
    except s3.exceptions.NoSuchKey:
        csv_lines = [['trnsc_id', 'trnsc_type', 'amt', 'trnsc_ts', 'notes']]
    except (BotoCoreError, ClientError) as e:
        print(f"[ERROR] Unable to read from S3: {e}")
        return

    # Append new row
    csv_lines.append([trnsc_id, trnsc_type, f"{amount:.2f}", trnsc_ts, notes])

    # Write back to S3
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_lines)
        s3.put_object(Bucket=bucket_name, Key=s3_key, Body=output.getvalue().encode('utf-8'))
    except (BotoCoreError, ClientError) as e:
        print(f"[ERROR] Unable to write to S3: {e}")




if __name__ == '__main__':
    app.run(debug=True)
