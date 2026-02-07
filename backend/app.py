from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
import requests
import pymysql
import os
from functools import wraps
from datetime import timedelta, date, datetime
from PIL import Image, ImageChops
import io
import json
import re
import hmac
import hashlib
import uuid

# Optional: try to use face_recognition for better matching. If not installed,
# fall back to simple RMS image-difference comparison implemented below.
import importlib
FACE_RECOG_AVAILABLE = False
try:
    # importlib used to avoid static import errors in editors when optional
    # packages are not installed. Pylance may still flag dynamic imports, so
    # we avoid top-level static imports for these optional libs.
    face_recognition = importlib.import_module('face_recognition')  # type: ignore
    np = importlib.import_module('numpy')  # type: ignore
    FACE_RECOG_AVAILABLE = True
except Exception as _err:
    FACE_RECOG_AVAILABLE = False
    print("[WARNING] face_recognition not available, falling back to RMS diff:", str(_err))

# Cached known encodings (loaded from reference image)
KNOWN_ENCODINGS = None

def _load_known_encodings(ref_path):
    """Load face encodings from the reference image file using face_recognition.
    Returns a list of encodings or empty list if none found or library unavailable.
    """
    global KNOWN_ENCODINGS
    if KNOWN_ENCODINGS is not None:
        return KNOWN_ENCODINGS

    KNOWN_ENCODINGS = []
    if not FACE_RECOG_AVAILABLE:
        return KNOWN_ENCODINGS

    try:
        # face_recognition expects RGB image data
        img = face_recognition.load_image_file(ref_path)
        encs = face_recognition.face_encodings(img)
        if encs:
            KNOWN_ENCODINGS = encs
        else:
            print("⚠️ No face encodings found in reference admin image.")
    except Exception as e:
        print(f"⚠️ Error loading reference encodings: {e}")

    return KNOWN_ENCODINGS

# Load environment variables from .env if python-dotenv is available
# Use dynamic import so static analyzers (like Pylance) don't flag missing
# optional dependency when it's not installed in the current environment.
try:
    import importlib
    dotenv_mod = importlib.import_module('dotenv')
    load_dotenv = getattr(dotenv_mod, 'load_dotenv')
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print('✅ Loaded environment variables from backend/.env')
    else:
        print('ℹ️ No backend/.env file found; using existing environment variables')
except Exception:
    # python-dotenv not installed — that's fine, environment variables can still be used
    print('ℹ️ python-dotenv not available; ensure environment variables are set')

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "../frontend"),
    static_folder=os.path.join(os.path.dirname(__file__), "../frontend/static"),
    static_url_path="/static"
)
app.secret_key = "super_secret_key"
app.permanent_session_lifetime = timedelta(hours=24)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("❌ Please login first.", "error")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("❌ Please login first.", "error")
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            flash("❌ Admin access required.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- Database Setup -----------------
db = None
cursor = None

def get_db():
    global db, cursor
    if db is None:
        try:
            db = pymysql.connect(
                host=os.getenv("DB_HOST", "localhost"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", "Ishwarya@123"),
                database=os.getenv("DB_NAME", "museum_db")
            )
            cursor = db.cursor()
        except Exception as e:
            print(f"[WARNING] Database connection failed: {e}")
            print(f"[INFO] Configure database via environment variables:")
            print(f"      DB_HOST={os.getenv('DB_HOST', 'not set')}")
            print(f"      DB_USER={os.getenv('DB_USER', 'not set')}")
            print(f"      DB_PASSWORD=***")
            print(f"      DB_NAME={os.getenv('DB_NAME', 'not set')}")
            db = None
            cursor = None
    return db, cursor

# Try to initialize database on startup
try:
    get_db()
except:
    pass

# ----------------- Flask-Mail Setup -----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ishwaryaganesan555@gmail.com'
# Read Mail password from environment for security
mail_password_env = os.environ.get('MAIL_PASSWORD')
if mail_password_env:
    app.config['MAIL_PASSWORD'] = mail_password_env
else:
    # Fallback to current value but warn the developer to set the env var
    app.config['MAIL_PASSWORD'] = 'kyuxefupzofaeiha'
    print("[WARNING] MAIL_PASSWORD environment variable not set. Using fallback Gmail App Password.")

app.config['MAIL_DEFAULT_SENDER'] = 'ishwaryaganesan555@gmail.com'

mail = Mail(app)


def send_via_sendgrid(to_emails, subject, body):
    """Send email via SendGrid API as a fallback. Expects SENDGRID_API_KEY env var."""
    api_key = os.environ.get('SENDGRID_API_KEY')
    if not api_key:
        print("⚠️ SendGrid API key not configured (SENDGRID_API_KEY).")
        return False, "SendGrid API key not configured"

    # Build SendGrid payload
    payload = {
        "personalizations": [{
            "to": [{"email": addr} for addr in (to_emails if isinstance(to_emails, list) else [to_emails])]
        }],
        "from": {"email": app.config.get('MAIL_DEFAULT_SENDER')},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}]
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post('https://api.sendgrid.com/v3/mail/send', json=payload, headers=headers, timeout=15)
        if resp.status_code in (200, 202):
            print(f"✅ SendGrid sent email to {to_emails}")
            return True, "Sent via SendGrid"
        else:
            print(f"❌ SendGrid failed: {resp.status_code} {resp.text}")
            return False, f"SendGrid error: {resp.status_code}"
    except Exception as e:
        print(f"❌ SendGrid exception: {e}")
        return False, str(e)

# ----------------- Database Initialization -----------------
# Initialize database on startup (only if tables don't exist)
def init_database():
    """Initialize database tables if they don't exist"""
    try:
        # Check if users table exists
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'museum_db' AND table_name = 'users'")
        users_exists = cursor.fetchone()
        
        # Check if tickets table exists
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'museum_db' AND table_name = 'tickets'")
        tickets_exists = cursor.fetchone()
        
        # Check if feedback table exists
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'museum_db' AND table_name = 'feedback'")
        feedback_exists = cursor.fetchone()
        
        # Only skip initialization if all tables exist
        if users_exists and tickets_exists and feedback_exists:
            return
        
        # Drop and recreate users table with new schema
        cursor.execute("DROP TABLE IF EXISTS users")
        print("⚠️ Dropped old users table")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                phone VARCHAR(15),
                role ENUM('user', 'admin') DEFAULT 'user',
                status ENUM('active', 'inactive') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email)
            )
        """)
        db.commit()
        print("✅ Database table 'users' created successfully")
        
        # Insert default admin user
        cursor.execute(
            """
            INSERT INTO users (name, email, password, phone, role, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("Administrator", "admin@gmail.com", "Admin@123", "9999999999", "admin", "active")
        )
        db.commit()
        print("✅ Admin user created")
        
        # Drop existing table to recreate with correct schema
        cursor.execute("DROP TABLE IF EXISTS tickets")
        print("⚠️ Dropped old tickets table")
        
        # Create new tickets table with correct schema
        cursor.execute("""
            CREATE TABLE tickets (
                id INT PRIMARY KEY AUTO_INCREMENT,
                ticket_code VARCHAR(100) UNIQUE,
                museum_name VARCHAR(255) NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                user_email VARCHAR(100) NOT NULL,
                visit_date DATE NOT NULL,
                visit_time TIME,
                ticket_qty INT DEFAULT 1,
                total_price DECIMAL(10, 2),
                booking_status ENUM('confirmed', 'cancelled', 'pending') DEFAULT 'confirmed',
                used BOOLEAN DEFAULT FALSE,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_museum (museum_name),
                INDEX idx_email (user_email),
                INDEX idx_date (visit_date),
                INDEX idx_code (ticket_code)
            )
        """)
        db.commit()
        print("✅ Database table 'tickets' created successfully")
        # Ensure legacy installations have the columns (noop if already created)
        try:
            cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'ticket_code'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_code VARCHAR(100) UNIQUE")
                db.commit()
            cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'used'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE tickets ADD COLUMN used BOOLEAN DEFAULT FALSE")
                db.commit()
        except Exception:
            pass
        # Create feedback table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_email VARCHAR(100),
                museum_name VARCHAR(255),
                rating INT,
                comments TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_museum (museum_name)
            )
        """)
        db.commit()
        print("✅ Database table 'feedback' ensured")
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")

# Initialize database only once on startup
init_database()

# Ensure tickets table has new columns (for existing installations)
def ensure_ticket_columns():
    try:
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'ticket_code'")
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_code VARCHAR(100) UNIQUE")
                db.commit()
                print('✅ Added column ticket_code to tickets')
            except Exception as e:
                print('⚠️ Could not add ticket_code:', e)
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'used'")
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute("ALTER TABLE tickets ADD COLUMN used BOOLEAN DEFAULT FALSE")
                db.commit()
                print('✅ Added column used to tickets')
            except Exception as e:
                print('⚠️ Could not add used:', e)
    except Exception as e:
        print('⚠️ Ensure ticket columns check failed:', e)

# Add optional columns for payments and audit if missing
def ensure_payment_columns():
    try:
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'payment_status'")
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute("ALTER TABLE tickets ADD COLUMN payment_status VARCHAR(32) DEFAULT 'pending'")
                db.commit()
                print('✅ Added column payment_status to tickets')
            except Exception as e:
                print('⚠️ Could not add payment_status:', e)
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = DATABASE() AND table_name = 'tickets' AND column_name = 'razorpay_order_id'")
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute("ALTER TABLE tickets ADD COLUMN razorpay_order_id VARCHAR(100) DEFAULT NULL")
                db.commit()
                print('✅ Added column razorpay_order_id to tickets')
            except Exception as e:
                print('⚠️ Could not add razorpay_order_id:', e)
    except Exception as e:
        print('⚠️ Ensure payment columns check failed:', e)

ensure_ticket_columns()
ensure_payment_columns()

# Configuration for Razorpay
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_your_key')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'rzp_test_your_secret')
TICKET_PRICE = int(os.environ.get('TICKET_PRICE', '50'))  # default ₹50 per ticket

# ----------------- ROUTES -----------------

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash("❌ Please fill in all fields.", "error")
            return redirect(url_for('login_page'))
        
        try:
            # Check if user exists
            cursor.execute(
                "SELECT id, name, role, status FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()
            
            if not user:
                # Auto-create new user with provided email
                cursor.execute(
                    """
                    INSERT INTO users (name, email, password, phone, role, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (email.split('@')[0], email, password, "", "user", "active")
                )
                db.commit()
                print(f"✅ New user created: {email}")
                
                # Fetch the newly created user
                cursor.execute(
                    "SELECT id, name, role, status FROM users WHERE email = %s",
                    (email,)
                )
                user = cursor.fetchone()
            else:
                # Existing user - verify password
                user_id, name, role, status = user
                cursor.execute(
                    "SELECT password FROM users WHERE id = %s",
                    (user_id,)
                )
                stored_password = cursor.fetchone()[0]
                
                if stored_password != password:
                    flash("❌ Invalid password.", "error")
                    return redirect(url_for('login_page'))
            
            user_id, name, role, status = user
            
            if status == 'inactive':
                flash("❌ Your account is inactive. Contact admin.", "error")
                return redirect(url_for('login_page'))
            
            # Set session
            session['user_id'] = user_id
            session['email'] = email
            session['name'] = name
            session['role'] = role
            session.permanent = True
            
            flash(f"✅ Welcome {name}!", "success")
            if role == 'admin':
                return redirect(url_for('admin_page'))
            else:
                return redirect(url_for('home'))
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            flash("❌ Login failed. Please try again.", "error")
            return redirect(url_for('login_page'))
    
    return render_template('login.html')

# Test Email Route (for debugging)
@app.route('/test_email')
def test_email():
    try:
        msg = Message(
            subject="Test Email - Museum Management System",
            recipients=['ishwaryaganesan555@gmail.com'],
            body="This is a test email from the Museum Management System. If you received this, email is working!"
        )
        mail.send(msg)
        return "✅ Test email sent successfully! Check your inbox (and spam folder)."
    except Exception as e:
        print(f"❌ TEST EMAIL ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        # Try SendGrid fallback
        try:
            ok, msg_text = send_via_sendgrid('ishwaryaganesan555@gmail.com', 'Test Email - Museum Management System', 'This is a test email from the Museum Management System (sent via SendGrid fallback).')
            if ok:
                return "✅ Test email sent via SendGrid fallback. Check your inbox."
            else:
                return f"❌ Email failed (SMTP): {type(e).__name__}: {str(e)} -- SendGrid: {msg_text}"
        except Exception as ex:
            print(f"❌ SendGrid fallback error: {ex}")
            return f"❌ Email failed: {type(e).__name__}: {str(e)} (also SendGrid fallback failed)"

# Home Page
@app.route('/home')
def home():
    return render_template('home.html')

# Ticket Booking
@app.route('/ticket', methods=['GET', 'POST'])
def ticket():
    if request.method == 'POST':
        museum_name = request.form.get('museum', '').strip()
        user_name = request.form.get('name', '').strip()
        user_email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        ticket_date = request.form.get('date', '').strip()
        ticket_time = request.form.get('time', '').strip()
        ticket_qty = request.form.get('tickets', '1')
        payment_method = request.form.get('payment_method', 'manual_upi').strip()  # ✅ Capture payment method
        
        # ✅ If user is logged in, use their session email for accurate tracking
        if session.get('email'):
            user_email = session.get('email')
            user_name = session.get('name', user_name)
        
        # Validation
        if not all([museum_name, user_name, user_email, phone, ticket_date]):
            flash("❌ Please fill in all required fields.", "error")
            return redirect(url_for('ticket', museum=museum_name))
        
        try:
            ticket_qty = int(ticket_qty) if ticket_qty else 1
        except ValueError:
            ticket_qty = 1

        # ✅ Calculate total price (₹10 per ticket for manual UPI)
        price_per_ticket = 10
        total_price = ticket_qty * price_per_ticket

        # ✅ Insert ticket into database with payment information
        try:
            # Update user's phone number if booking
            if user_email:
                cursor.execute(
                    "UPDATE users SET phone = %s WHERE email = %s AND (phone IS NULL OR phone = '')",
                    (phone, user_email)
                )
                db.commit()
            
            cursor.execute(
                """
                INSERT INTO tickets (museum_name, user_name, user_email, phone, visit_date, visit_time, ticket_qty, total_price, payment_method, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (museum_name, user_name, user_email, phone, ticket_date, ticket_time if ticket_time else None, ticket_qty, total_price, payment_method, 'completed')
            )
            db.commit()

            # Determine the inserted ticket id in a robust way
            try:
                ticket_id = int(cursor.lastrowid) if getattr(cursor, 'lastrowid', None) else None
            except Exception:
                ticket_id = None
            if not ticket_id:
                try:
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    ticket_id = int(cursor.fetchone()[0])
                except Exception:
                    ticket_id = None

            # Create a human-friendly ticket code and save it
            ticket_code = None
            if ticket_id:
                ticket_code = f"MUSEUM{1000 + int(ticket_id)}"
                try:
                    cursor.execute("UPDATE tickets SET ticket_code = %s WHERE id = %s", (ticket_code, ticket_id))
                    db.commit()
                except Exception as e:
                    print(f"⚠️ Failed to save ticket code: {e}")

            print(f"✅ Ticket booked: {user_name} | {museum_name} | {ticket_date} | Phone: {phone} | Code: {ticket_code} | Payment: {payment_method}")
            flash("✅ Ticket booked successfully!", "success")
            
            # Email sending (include ticket code and payment details)
            try:
                body = f"Hello {user_name},\n\nYour ticket for {museum_name} is booked successfully!\n\nDetails:\n- Museum: {museum_name}\n- Ticket Date: {ticket_date}\n- Time: {ticket_time if ticket_time else 'Not specified'}\n- Tickets: {ticket_qty}\n- Total Amount: ₹{total_price}\n- Payment Method: {payment_method.upper()}\n- Contact: {phone}\n"
                if ticket_code:
                    body += f"- Ticket Code: {ticket_code}\n"
                body += "\nThank you for visiting Tamil Nadu Museums!\n\nRegards,\nMuseum Management System\n"
                msg = Message(
                    subject="Ticket Confirmation - Tamil Nadu Museums",
                    recipients=[user_email],
                    body=body
                )
                mail.send(msg)
                print(f"✅ Confirmation email sent to {user_email}")
                flash("✅ Confirmation email sent.", "success")
            except Exception as e:
                print(f"⚠️ EMAIL ERROR: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                # Try SendGrid fallback
                try:
                    ok, sg_msg = send_via_sendgrid(user_email, "Ticket Confirmation - Tamil Nadu Museums", body)
                    if ok:
                        flash("✅ Ticket booked and confirmation sent via SendGrid.", "success")
                    else:
                        flash(f"⚠️ Ticket booked but email sending failed (SendGrid: {sg_msg}).", "warning")
                except Exception as ex:
                    print(f"❌ SendGrid fallback error: {ex}")
                    flash("⚠️ Ticket booked but email sending failed. Check console for details.", "warning")

            # Redirect to ticket confirmation page if we have a code
            if ticket_code:
                # If request is AJAX JSON, return ticket data so frontend can render QR immediately
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('ajax') == '1':
                    return jsonify({'success': True, 'ticket': {'code': ticket_code, 'id': ticket_id, 'museum': museum_name, 'name': user_name, 'date': ticket_date, 'time': ticket_time if ticket_time else '', 'qty': ticket_qty, 'payment_method': payment_method, 'total_price': total_price}}), 200
                return redirect(url_for('ticket_confirm', code=ticket_code))
        
        except pymysql.err.IntegrityError as e:
            print(f"❌ DATABASE INTEGRITY ERROR: {e}")
            flash("❌ This booking already exists. Please check your bookings.", "error")
        except pymysql.err.ProgrammingError as e:
            print(f"❌ DATABASE STRUCTURE ERROR: {e}")
            flash("❌ Database structure error. Please contact support.", "error")
        except Exception as e:
            print(f"❌ DATABASE ERROR: {type(e).__name__}: {e}")
            flash("❌ Error booking ticket. Please try again or contact support.", "error")
            
        return redirect(url_for('ticket', museum=museum_name))

    museum_name = request.args.get('museum', '')
    return render_template('ticket.html', museum=museum_name)

# Ticket confirmation page - shows QR and ticket details
@app.route('/ticket_confirm')
def ticket_confirm():
    code = request.args.get('code', '')
    if not code:
        flash("❌ Invalid ticket code.", "error")
        return redirect(url_for('ticket'))
    try:
        try:
            cursor.execute("SELECT id, ticket_code, museum_name, user_name, user_email, visit_date, visit_time, ticket_qty, total_price, payment_method, payment_status, booking_status, used FROM tickets WHERE ticket_code = %s", (code,))
            row = cursor.fetchone()
        except pymysql.err.ProgrammingError as pe:
            print(f"⚠️ Ticket confirm fallback due to DB schema: {pe}")
            # fallback: try to infer id from code
            maybe_id = None
            m = re.search(r"(\d+)", str(code))
            if m:
                num = int(m.group(1))
                if num > 1000:
                    maybe_id = num - 1000
            if maybe_id is not None:
                cursor.execute("SELECT id, museum_name, user_name, user_email, visit_date, visit_time, ticket_qty, total_price, payment_method, payment_status, booking_status FROM tickets WHERE id = %s", (maybe_id,))
                row = cursor.fetchone()
                if row:
                    row = (row[0], None, row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], 0)

        if not row:
            flash("❌ Ticket not found.", "error")
            return redirect(url_for('ticket'))
        ticket = {
            'id': row[0],
            'code': row[1],
            'museum': row[2],
            'name': row[3],
            'email': row[4],
            'date': str(row[5]),
            'time': str(row[6]) if row[6] else '',
            'qty': row[7],
            'total_price': float(row[8]) if row[8] else 0.0,
            'payment_method': row[9] if row[9] else 'manual_upi',
            'payment_status': row[10] if row[10] else 'completed',
            'status': row[11] if len(row) > 11 else 'confirmed',
            'used': bool(row[12]) if len(row) > 12 else False
        }
        return render_template('ticket_confirm.html', ticket=ticket)
    except Exception as e:
        print(f"❌ Ticket confirm error: {e}")
        flash("❌ Invalid ticket code.", "error")
        return redirect(url_for('ticket'))

# API: Create Razorpay order (payment initialization)
@app.route('/api/create_order', methods=['POST'])
def api_create_order():
    try:
        data = request.get_json() or {}
        museum = data.get('museum')
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        visit_date = data.get('date')
        visit_time = data.get('time') or None
        qty = int(data.get('tickets', 1))
        if not all([museum, name, email, visit_date]):
            return jsonify({'success': False, 'message': 'Missing booking details'}), 400

        # Quick check for placeholder keys
        if ('your_key' in (RAZORPAY_KEY_ID or '').lower()) or ('your_secret' in (RAZORPAY_KEY_SECRET or '').lower()):
            msg = 'Razorpay API keys not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET environment variables.'
            print('❌', msg)
            return jsonify({'success': False, 'message': msg}), 500

        # Calculate amount (in paise)
        total = int(TICKET_PRICE) * int(qty)
        amount_paise = int(total * 100)
        # Create Razorpay order
        payload = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'receipt_{uuid.uuid4().hex}',
            'payment_capture': 1
        }
        print(f"ℹ️ Creating Razorpay order: amount={amount_paise}, receipt={payload['receipt']}")
        try:
            r = requests.post('https://api.razorpay.com/v1/orders', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), json=payload, timeout=15)
        except requests.RequestException as re:
            print(f"❌ Razorpay request error: {re}")
            return jsonify({'success': False, 'message': 'Payment gateway request failed', 'detail': str(re)}), 502

        if r.status_code not in (200,201):
            # Log response body to help debugging (status, body)
            resp_text = r.text
            print(f"❌ Razorpay order creation failed: status={r.status_code}, body={resp_text}")
            # Return detailed message so frontend and logs have actionable info
            return jsonify({'success': False, 'message': 'Failed to create order with payment gateway', 'status': r.status_code, 'detail': resp_text}), 500

        try:
            order = r.json()
        except Exception as je:
            print(f"❌ Razorpay returned non-JSON response: {je} - body={r.text}")
            return jsonify({'success': False, 'message': 'Payment gateway returned unexpected response', 'detail': r.text}), 500

        return jsonify({'success': True, 'order': {'id': order.get('id'), 'amount': order.get('amount'), 'currency': order.get('currency')}, 'key_id': RAZORPAY_KEY_ID, 'amount_display': total}), 200
    except Exception as e:
        print(f"❌ Create order error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# Diagnostic endpoint: quick check of Razorpay API connectivity & key validity
@app.route('/api/razorpay_check')
def api_razorpay_check():
    try:
        if ('your_key' in (RAZORPAY_KEY_ID or '').lower()) or ('your_secret' in (RAZORPAY_KEY_SECRET or '').lower()):
            return jsonify({'success': False, 'message': 'Razorpay keys not configured (environment variables missing or placeholders present)'}), 400
        try:
            r = requests.get('https://api.razorpay.com/v1/payments?count=1', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), timeout=10)
        except requests.RequestException as re:
            return jsonify({'success': False, 'message': 'Could not reach Razorpay API', 'detail': str(re)}), 502
        return jsonify({'success': True, 'status': r.status_code, 'body_snippet': (r.text[:1000] if r.text else '')}), 200
    except Exception as e:
        print(f"❌ Razorpay check error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# API: Verify payment (called after successful Razorpay checkout)
@app.route('/api/verify_payment', methods=['POST'])
def api_verify_payment():
    try:
        data = request.get_json() or {}
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')
        # Booking details (sent from frontend) to create ticket after verification
        museum = data.get('museum')
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        visit_date = data.get('date')
        visit_time = data.get('time') or None
        qty = int(data.get('tickets', 1))

        if not all([payment_id, order_id, signature, museum, name, email, visit_date]):
            return jsonify({'success': False, 'message': 'Missing payment or booking details'}), 400

        # Verify signature
        msg = f"{order_id}|{payment_id}".encode()
        expected_sig = hmac.new(RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            print('❌ Razorpay signature mismatch')
            return jsonify({'success': False, 'message': 'Invalid signature'}), 400

        # Idempotency: if a ticket with this order id already exists, return it
        cursor.execute("SELECT id, ticket_code FROM tickets WHERE razorpay_order_id = %s", (order_id,))
        existing = cursor.fetchone()
        if existing:
            existing_ticket = {'id': existing[0], 'code': existing[1]}
            return jsonify({'success': True, 'ticket': existing_ticket}), 200

        # Create ticket record (payment verified)
        total_price = float(TICKET_PRICE) * qty
        cursor.execute(
            """
            INSERT INTO tickets (museum_name, user_name, user_email, visit_date, visit_time, ticket_qty, total_price, booking_status, payment_status, razorpay_order_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'confirmed', 'paid', %s)
            """,
            (museum, name, email, visit_date, visit_time if visit_time else None, qty, total_price, order_id)
        )
        db.commit()
        # Fetch inserted id
        try:
            ticket_id = int(cursor.lastrowid) if getattr(cursor, 'lastrowid', None) else None
        except Exception:
            ticket_id = None
        if not ticket_id:
            cursor.execute("SELECT LAST_INSERT_ID()"); ticket_id = int(cursor.fetchone()[0])

        ticket_code = f"MUSEUM{1000 + int(ticket_id)}"
        try:
            cursor.execute("UPDATE tickets SET ticket_code = %s WHERE id = %s", (ticket_code, ticket_id))
            db.commit()
        except Exception as e:
            print(f"⚠️ Failed to save ticket code after payment: {e}")

        # Send confirmation email (reuse existing pattern)
        try:
            body = f"Hello {name},\n\nYour payment of ₹{total_price} has been received and your ticket is confirmed!\n\nDetails:\n- Museum: {museum}\n- Ticket Date: {visit_date}\n- Tickets: {qty}\n- Ticket Code: {ticket_code}\n\nThank you for visiting Tamil Nadu Museums!\n\nRegards,\nMuseum Management System\n"
            msg = Message(subject="Ticket Confirmation - Tamil Nadu Museums", recipients=[email], body=body)
            mail.send(msg)
        except Exception as e:
            print(f"⚠️ Email after payment failed: {e}")

        return jsonify({'success': True, 'ticket': {'id': ticket_id, 'code': ticket_code, 'museum': museum, 'name': name, 'date': visit_date, 'time': visit_time if visit_time else '', 'qty': qty}}), 200

    except Exception as e:
        print(f"❌ Verify payment error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# API: Verify ticket (accepts scanned data or ticket code)
@app.route('/api/verify_ticket', methods=['POST'])
def api_verify_ticket():
    try:
        data = request.get_json() or {}
        raw = data.get('data') or data.get('token') or data.get('ticket_code') or data.get('code') or ''
        mark_used = data.get('mark_used', True)
        if not raw:
            return jsonify({'success': False, 'message': 'No ticket data provided'}), 400
        ticket_code = None
        # Try to parse JSON content from QR
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                ticket_code = parsed.get('ticket_code') or parsed.get('code') or parsed.get('TicketID') or parsed.get('id')
        except Exception:
            ticket_code = raw.strip()

        if not ticket_code:
            return jsonify({'success': False, 'message': 'Invalid ticket payload'}), 400

        # Attempt regular lookup (ticket_code + used columns may not exist on older databases)
        try:
            cursor.execute("SELECT id, ticket_code, museum_name, user_name, user_email, visit_date, visit_time, ticket_qty, booking_status, used FROM tickets WHERE ticket_code = %s OR id = %s", (ticket_code, ticket_code))
            row = cursor.fetchone()
        except pymysql.err.ProgrammingError as pe:
            # Schema mismatch (e.g., ticket_code or used missing). Try fallback lookups.
            print(f"⚠️ Verify fallback (DB schema issue): {pe}")
            row = None
            maybe_id = None
            # If code is numeric, try it as id
            if str(ticket_code).isdigit():
                maybe_id = int(ticket_code)
            else:
                # Parse digits from code like MUSEUM1003 -> id = 1003 - 1000 = 3
                m = re.search(r"(\d+)", str(ticket_code))
                if m:
                    num = int(m.group(1))
                    if num > 1000:
                        maybe_id = num - 1000
            if maybe_id is not None:
                cursor.execute("SELECT id, museum_name, user_name, user_email, visit_date, visit_time, ticket_qty, booking_status FROM tickets WHERE id = %s", (maybe_id,))
                row = cursor.fetchone()
                if row:
                    # normalize to expected tuple length by inserting placeholders for missing fields (ticket_code, used)
                    row = (row[0], None, row[1], row[2], row[3], row[4], row[5], row[6], row[7], 0)

        if not row:
            return jsonify({'success': False, 'message': 'Ticket not found'}), 404

        # Normalize row to ticket dict safely
        ticket = {
            'id': row[0],
            'code': row[1] if len(row) > 1 else None,
            'museum': row[2] if len(row) > 2 else None,
            'name': row[3] if len(row) > 3 else None,
            'email': row[4] if len(row) > 4 else None,
            'date': row[5] if len(row) > 5 else None,
            'time': str(row[6]) if len(row) > 6 and row[6] else '',
            'qty': row[7] if len(row) > 7 else None,
            'status': row[8] if len(row) > 8 else None,
            'used': bool(row[9]) if len(row) > 9 else False
        }

        # Validation checks
        if ticket['status'] != 'confirmed':
            return jsonify({'success': False, 'message': f"Booking status: {ticket['status']}"}), 400

        today = date.today()
        if ticket['date'] != today and str(ticket['date']) != str(today):
            return jsonify({'success': False, 'message': 'Ticket date does not match today (expired / not valid today)'}), 400

        if ticket['used']:
            return jsonify({'success': False, 'message': 'Ticket already used'}), 400

        # Mark as used if requested
        if mark_used:
            try:
                cursor.execute("UPDATE tickets SET used = TRUE WHERE id = %s", (ticket['id'],))
                db.commit()
            except Exception as e:
                print(f"⚠️ Failed to mark ticket used: {e}")

        return jsonify({'success': True, 'message': 'Entry allowed', 'ticket': ticket}), 200
    except Exception as e:
        print(f"❌ Verify ticket error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Verify page (camera scanner for staff)
@app.route('/verify')
def verify_page():
    return render_template('scan.html')

# Favicon route to avoid 404 noise
@app.route('/favicon.ico')
def favicon_route():
    # Return empty 204 to avoid 404 in browser console when no favicon present
    return ('', 204)

# Map View
@app.route('/map')
def map_view():
    return render_template('map.html')

# Artifact View
@app.route('/artifact')
def artifact_view():
    return render_template('artifact.html')

# Feedback View
@app.route('/feedback')
def feedback_view():
    return render_template('feedback.html')

# Admin Page
@app.route('/admin')
@admin_required
def admin_page():
    # Require admin face verification (or password) before showing admin panel
    if not session.get('admin_verified'):
        return redirect(url_for('admin_unlock_page'))
    return render_template('admin.html')


# Admin face-unlock page (captures webcam image client-side and can fallback to password)
@app.route('/admin_unlock', methods=['GET'])
@admin_required
def admin_unlock_page():
    # Clear any previous verification flag
    session.pop('admin_verified', None)
    return render_template('admin_face_unlock.html')


def _rms_diff(img1, img2, size=(200, 200)):
    """Compute RMS difference between two PIL images."""
    try:
        im1 = img1.convert('L').resize(size)
        im2 = img2.convert('L').resize(size)
        diff = ImageChops.difference(im1, im2)
        h = diff.histogram()
        sq = (value * (i % 256) ** 2 for i, value in enumerate(h))
        sum_sq = sum(sq)
        rms = (sum_sq / float(im1.size[0] * im1.size[1])) ** 0.5
        return rms
    except Exception:
        return float('inf')


# API endpoint: receive captured image and compare with reference admin image
@app.route('/api/verify_face', methods=['POST'])
@admin_required
def api_verify_face():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image uploaded'}), 400

        file = request.files['image']
        img_bytes = file.read()
        captured = Image.open(io.BytesIO(img_bytes))

        # Reference image path (admin face). Developer should place an image at this path.
        ref_path = os.path.join(os.path.dirname(__file__), '../frontend/static/images/admin_face.jpg')
        if not os.path.exists(ref_path):
            # Reference image not found - auto-verify since we don't have a reference to compare against
            session['admin_verified'] = True
            return jsonify({'success': True, 'message': 'Face image accepted (reference image not found, auto-verified)'}), 200

        # Try to use face_recognition when available for more reliable matching
        if FACE_RECOG_AVAILABLE:
            # Ensure known encodings loaded
            known = _load_known_encodings(ref_path)
            if not known:
                # No encodings available in reference image -> fall back
                print("⚠️ No known encodings; falling back to RMS diff")
            else:
                try:
                    # Convert captured PIL image to RGB numpy array
                    captured_rgb = np.array(captured.convert('RGB'))
                    captured_encs = face_recognition.face_encodings(captured_rgb)
                    if not captured_encs:
                        return jsonify({'success': False, 'message': 'No face detected in captured image'}), 401

                    # Compare first detected face against known encodings
                    match = face_recognition.compare_faces(known, captured_encs[0], tolerance=0.55)
                    if any(match):
                        session['admin_verified'] = True
                        return jsonify({'success': True, 'message': 'Face verified (face_recognition)'})
                    else:
                        # continue to RMS fallback below
                        print('❌ face_recognition: no match')
                except Exception as e:
                    print(f"⚠️ face_recognition error: {e} -- falling back to RMS")

        # Fallback: compare using simple RMS image difference
        ref_img = Image.open(ref_path)
        rms = _rms_diff(ref_img, captured)

        # Threshold - lower is more strict. Adjust as needed.
        THRESHOLD = 30.0
        if rms < THRESHOLD:
            session['admin_verified'] = True
            return jsonify({'success': True, 'message': 'Face verified (RMS fallback)'})
        else:
            return jsonify({'success': False, 'message': 'Face did not match', 'rms': rms}), 401

    except Exception as e:
        print(f"❌ Face verification error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# API endpoint: verify admin password fallback
@app.route('/api/admin_verify_password', methods=['POST'])
@admin_required
def api_admin_verify_password():
    try:
        data = request.get_json() or {}
        password = data.get('password', '').strip()
        if not password:
            return jsonify({'success': False, 'message': 'Password required'}), 400

        user_id = session.get('user_id')
        cursor.execute('SELECT password FROM users WHERE id = %s', (user_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        stored_password = row[0]
        if stored_password == password:
            session['admin_verified'] = True
            return jsonify({'success': True, 'message': 'Password verified'})
        else:
            return jsonify({'success': False, 'message': 'Invalid password'}), 401

    except Exception as e:
        print(f"❌ Password verify error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Admin Users Page
@app.route('/admin_users')
@admin_required
def admin_users():
    return render_template('admin_users.html')

# Admin Museums Page
@app.route('/admin_museums')
@admin_required
def admin_museums():
    return render_template('admin_museums.html')

# Admin Bookings Page
@app.route('/admin_bookings')
@admin_required
def admin_bookings():
    return render_template('admin_bookings.html')

# Admin Dashboard Page
@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

# Admin Add Admin Page
@app.route('/admin_add_admin')
@admin_required
def admin_add_admin():
    return render_template('admin_add_admin.html')

# API: Add new admin
@app.route('/api/add_admin', methods=['POST'])
@admin_required
def add_admin_api():
    try:
        # Support both JSON and multipart/form-data (file uploads from camera capture)
        name = email = username = password = None
        # If form-data with files
        if request.files or request.form:
            form = request.form
            name = form.get('name', '').strip()
            email = form.get('email', '').strip().lower()
            username = form.get('username', '').strip()
            password = form.get('password', '').strip()
        else:
            data = request.get_json(force=False)
            if not data:
                return {"success": False, "message": "No data provided"}, 400
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()

        # Validation
        if not all([name, email, username, password]):
            return {"success": False, "message": "All fields are required"}, 400

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return {"success": False, "message": "Email already exists"}, 400

        # If an image was uploaded, save it to static/images
        saved_image_path = None
        if 'face_image' in request.files:
            img = request.files['face_image']
            if img and img.filename:
                images_dir = os.path.join(app.static_folder, 'images')
                os.makedirs(images_dir, exist_ok=True)
                # sanitize filename
                base_fn = f"admin_{username or email.split('@')[0]}"
                fn = f"{base_fn}.jpg"
                save_path = os.path.join(images_dir, fn)
                try:
                    img.save(save_path)
                    saved_image_path = f"/static/images/{fn}"
                except Exception as e:
                    print(f"⚠️ Failed to save uploaded image: {e}")

        # Insert new admin (note: users table has no image column; we simply store file)
        cursor.execute(
            """
            INSERT INTO users (name, email, password, phone, role, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, email, password, "", "admin", "active")
        )
        db.commit()

        resp = {"success": True, "message": "Admin added successfully"}
        if saved_image_path:
            resp['image'] = saved_image_path
        return resp, 201

    except Exception as e:
        print(f"❌ Error adding admin: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}, 500

# API: Get all admins
@app.route('/api/admins', methods=['GET'])
@admin_required
def get_admins_api():
    try:
        cursor.execute("""
            SELECT id, name, email, CONCAT(SUBSTR(email, 1, 3), '***') as username
            FROM users WHERE role = 'admin'
        """)
        admins = cursor.fetchall()
        admin_list = [
            {"id": a[0], "name": a[1], "email": a[2], "username": a[3]}
            for a in admins
        ]
        return {"success": True, "admins": admin_list}, 200
        
    except Exception as e:
        print(f"❌ Error fetching admins: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}, 500

# API: Delete admin
@app.route('/api/delete_admin/<int:admin_id>', methods=['DELETE'])
@admin_required
def delete_admin_api(admin_id):
    try:
        # Prevent deleting the last admin
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count <= 1:
            return {"success": False, "message": "Cannot delete the last admin"}, 400
        
        cursor.execute("DELETE FROM users WHERE id = %s AND role = 'admin'", (admin_id,))
        db.commit()
        
        return {"success": True, "message": "Admin deleted successfully"}, 200
        
    except Exception as e:
        print(f"❌ Error deleting admin: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}, 500

# Delete Admin by Email (API endpoint for manual deletion)
@app.route('/api/delete_admin_by_email', methods=['DELETE'])
@admin_required
def delete_admin_by_email():
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        
        if not email:
            return {"success": False, "error": "Email is required"}, 400
        
        # Prevent deleting the last admin
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count <= 1:
            return {"success": False, "error": "Cannot delete the last admin"}, 400
        
        # Check if admin with this email exists
        # Some schemas may not have 'username' column; select only common columns.
        cursor.execute("SELECT id, name FROM users WHERE email = %s AND role = 'admin'", (email,))
        admin = cursor.fetchone()

        if not admin:
            return {"success": False, "error": "Admin with this email not found"}, 404

        admin_id, admin_name = admin

        # Delete the admin by id
        cursor.execute("DELETE FROM users WHERE id = %s AND role = 'admin'", (admin_id,))
        db.commit()
        
        print(f"✅ Admin deleted: {admin_name} ({email})")
        return {"success": True, "message": f"Admin '{admin_name}' deleted successfully"}, 200
        
    except Exception as e:
        print(f"❌ Error deleting admin by email: {e}")
        return {"success": False, "error": f"Error: {str(e)}"}, 500

# Get all users (API endpoint for admin)
@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    try:
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.phone, u.role, u.status, COALESCE(COUNT(t.id), 0) as total_bookings, 
                   COALESCE(MAX(t.museum_name), '---') as last_museum 
            FROM users u 
            LEFT JOIN tickets t ON u.email = t.user_email 
            WHERE u.role = 'user'
            GROUP BY u.id, u.name, u.email, u.phone, u.role, u.status
            ORDER BY u.created_at DESC
        """)
        users = cursor.fetchall()
        
        # Convert to list of dictionaries
        user_list = []
        for user in users:
            user_list.append({
                'id': user[0],
                'name': user[1],
                'email': user[2],
                'phone': user[3] or '---',
                'role': user[4],
                'status': user[5],
                'total_bookings': int(user[6]) if user[6] else 0,
                'last_museum': user[7] if user[7] and user[7] != '---' else '---'
            })
        
        return {"users": user_list}
    except Exception as e:
        print(f"⚠️ Error fetching users: {e}")
        return {"users": [], "error": str(e)}

# Get all bookings (API endpoint for admin)
@app.route('/api/bookings', methods=['GET'])
@admin_required
def get_bookings():
    try:
        cursor.execute("SELECT id, user_name, user_email, museum_name, visit_date, visit_time, ticket_qty, booking_status, booked_at FROM tickets ORDER BY booked_at DESC")
        bookings = cursor.fetchall()
        
        # Convert to list of dictionaries
        booking_list = []
        for booking in bookings:
            booking_list.append({
                'id': booking[0],
                'user': booking[1],
                'email': booking[2],
                'phone': '---',
                'museum': booking[3],
                'date': str(booking[4]),
                'time': str(booking[5]) if booking[5] else '---',
                'tickets': booking[6],
                'status': booking[7],
                'bookingDate': str(booking[8]).split()[0] if booking[8] else '---'
            })
        
        return {"bookings": booking_list}
    except Exception as e:
        print(f"⚠️ Error fetching bookings: {e}")
        return {"bookings": [], "error": str(e)}

# Get all museums (API endpoint for admin)
@app.route('/api/museums', methods=['GET'])
@admin_required
def get_museums():
    try:
        # Total museums from the static list in admin_museums.html
        total_museums = 64
        
        return {"museums": [], "count": total_museums}
    except Exception as e:
        print(f"⚠️ Error fetching museums: {e}")
        return {"museums": [], "count": 0, "error": str(e)}


# Submit feedback for a museum
@app.route('/api/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.get_json() or {}
        museum = data.get('museum', '').strip()
        rating = data.get('rating')
        comments = data.get('comments', '').strip()
        user_email = session.get('email') or data.get('email') or None

        if not museum:
            return jsonify({'success': False, 'message': 'Museum name required'}), 400

        try:
            rating = int(rating)
        except Exception:
            rating = 0

        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400

        cursor.execute(
            "INSERT INTO feedback (user_email, museum_name, rating, comments) VALUES (%s, %s, %s, %s)",
            (user_email, museum, rating, comments)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Feedback submitted'}), 201
    except Exception as e:
        print(f"❌ Error submitting feedback: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# Get feedback for a museum
@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    try:
        museum = request.args.get('museum', '').strip()
        if not museum:
            return jsonify({'success': False, 'message': 'Museum name required'}), 400

        # Create fresh connection with correct credentials
        conn = pymysql.connect(
            host="localhost",
            user="root",
            password="Ishwarya@123",
            database="museum_db"
        )
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT user_email, rating, comments, submitted_at FROM feedback WHERE museum_name = %s ORDER BY submitted_at DESC LIMIT 200",
                (museum,)
            )
            rows = cur.fetchall()
            feedbacks = []
            for r in rows:
                feedbacks.append({
                    'user_email': r[0],
                    'rating': int(r[1]) if r[1] is not None else None,
                    'comments': r[2],
                    'submitted_at': str(r[3])
                })

            # summary
            cur.execute("SELECT AVG(rating), COUNT(*) FROM feedback WHERE museum_name = %s", (museum,))
            avg_row = cur.fetchone()
            avg = float(avg_row[0]) if avg_row and avg_row[0] is not None else 0.0
            count = int(avg_row[1]) if avg_row and avg_row[1] is not None else 0

            return jsonify({'success': True, 'feedbacks': feedbacks, 'average': round(avg,2), 'count': count})
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"❌ Error fetching feedback: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
    return jsonify({'success': False, 'message': 'Unknown error'}), 500

# Update booking status (API endpoint)
@app.route('/api/update-booking', methods=['POST'])
@admin_required
def update_booking():
    try:
        data = request.get_json()
        booking_id = data.get('id')
        status = data.get('status')
        
        cursor.execute(
            "UPDATE tickets SET booking_status = %s WHERE id = %s",
            (status, booking_id)
        )
        db.commit()
        return {"success": True, "message": f"Booking {booking_id} updated to {status}"}
    except Exception as e:
        print(f"⚠️ Error updating booking: {e}")
        return {"success": False, "error": str(e)}

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("✅ Logged out successfully.", "success")
    return redirect(url_for('login_page'))

# Serve museums_data.js
@app.route('/museums_data.js')
def serve_museums_data():
    try:
        with open(os.path.join(os.path.dirname(__file__), "../frontend/museums_data.js"), 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'application/javascript'}
    except Exception as e:
        print(f"⚠️ Error serving museums_data.js: {e}")
        return "console.log('Error loading museums data');", 404

# Root redirect to login
@app.route('/')
def root():
    return redirect(url_for('login_page'))

# ----------------- START SERVER -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
