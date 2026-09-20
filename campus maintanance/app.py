from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3
import random
import os
import csv
from datetime import datetime

# Matplotlib setup for headless rendering
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'campus_maintenance_secret_key_2026'

DB_FILE = 'campus_maintenance.db'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enrollment_no TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            is_verified INTEGER DEFAULT 0
        )
    ''')
    
    # Tickets / Complaints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id TEXT PRIMARY KEY,
            enrollment_no TEXT,
            student_name TEXT,
            department TEXT,
            building TEXT,
            room_no TEXT,
            category TEXT,
            problem TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Pending',
            date TEXT,
            admin_remarks TEXT DEFAULT ''
        )
    ''')

    # Ensure Default Admin Account Exists
    cursor.execute("SELECT * FROM users WHERE email = 'admin@campus.edu'")
    admin_user = cursor.fetchone()
    if not admin_user:
        cursor.execute('''
            INSERT INTO users (name, enrollment_no, email, password, role, is_verified)
            VALUES ('Admin', 'ADMIN001', 'admin@campus.edu', 'admin123', 'admin', 1)
        ''')
    
    conn.commit()
    conn.close()

init_db()

# --- CHART GENERATION FOR REPORTS ---
def generate_charts():
    os.makedirs('static/charts', exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 1. Status Distribution
    cursor.execute("SELECT status, COUNT(*) FROM complaints GROUP BY status")
    status_data = cursor.fetchall()
    
    plt.figure(figsize=(5, 4))
    if status_data:
        labels, counts = zip(*status_data)
        plt.pie(counts, labels=labels, autopct='%1.1f%%', colors=['#f97316', '#5F3475', '#48bb78'])
    else:
        plt.text(0.5, 0.5, 'No Ticket Data Available', horizontalalignment='center', verticalalignment='center')
    plt.title('Tickets by Status')
    plt.tight_layout()
    plt.savefig('static/charts/status_distribution.png')
    plt.close()

    # 2. Complaints by Building
    cursor.execute("SELECT building, COUNT(*) FROM complaints GROUP BY building")
    building_data = cursor.fetchall()
    
    plt.figure(figsize=(5, 4))
    if building_data:
        b_labels, b_counts = zip(*building_data)
        plt.bar(b_labels, b_counts, color='#42e8d3')
    else:
        plt.text(0.5, 0.5, 'No Building Data Available', horizontalalignment='center', verticalalignment='center')
    plt.title('Complaints by Building')
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig('static/charts/complaints_building.png')
    plt.close()

    conn.close()

# --- ROUTES ---

@app.route('/')
def dashboard():
    return render_template('index.html', active_tab='hero')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        enrollment_no = request.form['enrollment_no']
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (name, enrollment_no, email, password, role, is_verified)
                VALUES (?, ?, ?, ?, 'student', 0)
            ''', (name, enrollment_no, email, password))
            conn.commit()

            otp = random.randint(100000, 999999)
            session['otp'] = str(otp)
            session['temp_email'] = email
            flash(f"Verification OTP code sent! (Mock OTP: {otp})", 'info')
            return redirect(url_for('verify_otp', email=email))

        except sqlite3.IntegrityError:
            flash("Enrollment number or email already registered!", "danger")
        finally:
            conn.close()

    return render_template('index.html', active_tab='signup')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    email = request.args.get('email', session.get('temp_email'))
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_verified = 1 WHERE email = ?", (email,))
            conn.commit()
            conn.close()

            flash("Account verified successfully! You can now login.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP code! Please try again.", "danger")

    return render_template('index.html', active_tab='verify_otp', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE (email = ? OR enrollment_no = ?) AND password = ?
        ''', (identifier, identifier, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = {
                'id': user[0],
                'name': user[1],
                'enrollment_no': user[2],
                'email': user[3],
                'role': user[5]
            }
            flash(f"Welcome back, {user[1]}!", "success")
            return redirect(url_for('tickets'))
        else:
            flash("Invalid login credentials!", "danger")

    return render_template('index.html', active_tab='login')

@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_name = request.form['student_name']
        department = request.form['department']
        building = request.form['building']
        room_no = request.form['room_no']
        category = request.form['category']
        priority = request.form['priority']
        problem = request.form['problem']

        ticket_id = f"CMP{random.randint(100, 999)}"
        enrollment_no = session.get('user', {}).get('enrollment_no', 'STUDENT')
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO complaints 
            (id, enrollment_no, student_name, department, building, room_no, category, problem, priority, status, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
        ''', (ticket_id, enrollment_no, student_name, department, building, room_no, category, problem, priority, date_str))
        conn.commit()
        conn.close()

        generate_charts()
        flash(f"Maintenance issue registered! Ticket ID: {ticket_id}", "success")
        return redirect(url_for('tickets'))

    return render_template('index.html', active_tab='register')

@app.route('/tickets')
def tickets():
    search_query = request.args.get('search', '')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if search_query:
        cursor.execute('''
            SELECT * FROM complaints 
            WHERE id LIKE ? OR building LIKE ? OR category LIKE ? OR student_name LIKE ?
        ''', (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM complaints ORDER BY date DESC")

    rows = cursor.fetchall()
    conn.close()

    tickets_list = []
    for r in rows:
        tickets_list.append({
            'id': r[0],
            'enrollment_no': r[1],
            'student_name': r[2],
            'department': r[3],
            'building': r[4],
            'room_no': r[5],
            'category': r[6],
            'problem': r[7],
            'priority': r[8],
            'status': r[9],
            'date': r[10]
        })

    return render_template('index.html', active_tab='tickets', tickets=tickets_list, search_query=search_query)

@app.route('/admin_verify', methods=['GET', 'POST'])
def admin_verify():
    if not session.get('user') or session['user'].get('role') != 'admin':
        flash("Admin access required. Log in with admin credentials.", "danger")
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if request.method == 'POST':
        complaint_id = request.form['complaint_id']
        status = request.form['status']
        admin_remarks = request.form.get('admin_remarks', '')

        cursor.execute('''
            UPDATE complaints SET status = ?, admin_remarks = ? WHERE id = ?
        ''', (status, admin_remarks, complaint_id))
        conn.commit()
        generate_charts()
        flash(f"Ticket {complaint_id} status updated to '{status}'", "success")

    cursor.execute("SELECT * FROM complaints ORDER BY date DESC")
    complaints_list = cursor.fetchall()
    conn.close()

    return render_template('index.html', active_tab='admin_verify', complaints_list=complaints_list)

@app.route('/reports')
def reports():
    if not session.get('user') or session['user'].get('role') != 'admin':
        flash("Access restricted to Admins only.", "danger")
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'")
    in_progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    resolved = cursor.fetchone()[0]

    conn.close()
    generate_charts()

    return render_template('index.html', active_tab='reports', total=total, pending=pending, in_progress=in_progress, resolved=resolved)

@app.route('/export_csv')
def export_csv():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints")
    rows = cursor.fetchall()
    conn.close()

    filename = "maintenance_report.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Ticket ID', 'Enrollment', 'Student Name', 'Department', 'Building', 'Room', 'Category', 'Problem', 'Priority', 'Status', 'Date', 'Admin Remarks'])
        writer.writerows(rows)

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)