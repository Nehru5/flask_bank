from flask import Flask, render_template, request, redirect, url_for, session, send_file
import mysql.connector
import random
import datetime
import csv
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
import os


app = Flask(__name__)
app.secret_key = "bank_secret_key"

# ================================
# MySQL Connection
# ================================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Nehruraja@12345",
        database="banking_db"
    )

# ================================
# HOME
# ================================
@app.route('/')
def home():
    return render_template('home.html')

# ================================
# CREATE ACCOUNT
# ================================
@app.route('/create', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        balance = float(request.form.get('balance'))
        account_no = random.randint(1000000000, 9999999999)

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO accounts (account_no, name, email, password, balance)
            VALUES (%s, %s, %s, %s, %s)
        """, (account_no, name, email, password, balance))
        db.commit()
        cur.close()
        db.close()

        return render_template('account_created.html', account_no=account_no)

    return render_template('create.html')

# ================================
# LOGIN
# ================================
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    error = None
    if request.method == 'POST':
        acc = request.form.get('account_no')
        password = request.form.get('password')

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT * FROM accounts WHERE account_no=%s AND password=%s",
            (acc, password)
        )
        user = cur.fetchone()
        cur.close()
        db.close()

        if user:
            session['acc'] = acc
            return redirect(url_for('services'))
        else:
            error = "Invalid Account Number or Password"

    return render_template('dashboard.html', error=error)

# ================================
# DASHBOARD / SERVICES
# ================================
# ================================
# DASHBOARD / SERVICES
# ================================
@app.route('/services')
def services():
    if 'acc' not in session:
        return redirect(url_for('dashboard'))

    acc = session['acc']
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Get user info
    cur.execute("SELECT name, balance FROM accounts WHERE account_no=%s", (acc,))
    user = cur.fetchone()

    # Get transaction history for chart
    cur.execute("""
        SELECT type, amount, date 
        FROM transactions 
        WHERE account_no=%s 
        ORDER BY date ASC
    """, (acc,))
    transactions = cur.fetchall()

    cur.close()
    db.close()

    return render_template('services.html',
                           acc=acc,
                           name=user['name'],
                           balance=user['balance'],
                           transactions=transactions)


# ================================
# DEPOSIT
# ================================
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        acc = session['acc']

        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_no=%s", (amount, acc))
        cur.execute("INSERT INTO transactions (account_no, type, amount, date) VALUES (%s,'DEPOSIT',%s,%s)",
                    (acc, amount, datetime.datetime.now()))
        db.commit()
        cur.close()
        db.close()

        return redirect(url_for('services'))

    return render_template('deposit.html')

# ================================
# WITHDRAW
# ================================
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        acc = session['acc']

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT balance FROM accounts WHERE account_no=%s", (acc,))
        bal = cur.fetchone()[0]

        if bal >= amount:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_no=%s", (amount, acc))
            cur.execute("INSERT INTO transactions VALUES (NULL,%s,'WITHDRAW',%s,%s)",
                        (acc, amount, datetime.datetime.now()))
            db.commit()

        cur.close()
        db.close()
        return redirect(url_for('services'))

    return render_template('withdraw.html')

# ================================
# TRANSFER
# ================================
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'acc' not in session:
        return redirect(url_for('dashboard'))

    from_acc = session['acc']
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Get all accounts except current user
    cur.execute("SELECT account_no, name FROM accounts WHERE account_no != %s", (from_acc,))
    accounts = cur.fetchall()

    if request.method == 'POST':
        to_acc = request.form.get('to_acc')
        amount = float(request.form.get('amount'))

        # Check balance
        cur.execute("SELECT balance FROM accounts WHERE account_no=%s", (from_acc,))
        bal = cur.fetchone()['balance']

        if bal >= amount:
            # Deduct from sender
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_no=%s", (amount, from_acc))
            # Add to receiver
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_no=%s", (amount, to_acc))
            # Record transaction for sender
            cur.execute("INSERT INTO transactions (account_no, type, amount, date) VALUES (%s,'TRANSFER',%s,%s)",
                        (from_acc, amount, datetime.datetime.now()))
            # Record transaction for receiver
            cur.execute("INSERT INTO transactions (account_no, type, amount, date) VALUES (%s,'DEPOSIT',%s,%s)",
                        (to_acc, amount, datetime.datetime.now()))
            db.commit()

        cur.close()
        db.close()
        return redirect(url_for('services'))

    cur.close()
    db.close()
    return render_template('transfer.html', accounts=accounts)


# ================================
# TRANSACTION HISTORY
# ================================
@app.route('/history')
def history():
    acc = session['acc']
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM transactions WHERE account_no=%s ORDER BY date DESC", (acc,))
    data = cur.fetchall()
    cur.close()
    db.close()
    return render_template('history.html', data=data)

# ================================
# DOWNLOAD STATEMENT
# ================================
@app.route('/download')
def download():
    acc = session['acc']

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT type, amount, date FROM transactions WHERE account_no=%s ORDER BY date DESC", (acc,))
    rows = cur.fetchall()

    cur.execute("SELECT name FROM accounts WHERE account_no=%s", (acc,))
    name = cur.fetchone()[0]

    cur.close()
    db.close()

    file_path = "statement.pdf"
    pdf = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # ===== LOGO =====
    logo_path = os.path.join("static", "logo.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, 1.5*inch, 1.5*inch)
        elements.append(logo)

    elements.append(Spacer(1, 12))

    # ===== BANK NAME =====
    elements.append(Paragraph(
        "<b><font size=16>PyBANK</font></b>",
        styles['Title']
    ))

    elements.append(Spacer(1, 12))

    # ===== ACCOUNT INFO =====
    elements.append(Paragraph(f"<b>Account Holder:</b> {name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Account Number:</b> {acc}", styles['Normal']))
    elements.append(Paragraph(
        f"<b>Statement Generated:</b> {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}",
        styles['Normal']
    ))

    elements.append(Spacer(1, 20))

    # ===== TRANSACTION TABLE =====
    data = [["Type", "Amount (₹)", "Date"]]

    for row in rows:
        data.append([
            row[0],
            f"₹ {row[1]}",
            row[2].strftime('%d-%m-%Y %H:%M')
        ])

    table = Table(data, colWidths=[2*inch, 2*inch, 2.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # ===== FOOTER =====
    elements.append(Paragraph(
        "<i>This is a system-generated statement. No signature required.</i>",
        styles['Italic']
    ))

    pdf.build(elements)

    return send_file(file_path, as_attachment=True)

# ================================
# LOGOUT
# ================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
