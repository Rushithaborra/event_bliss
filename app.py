from flask import Flask, render_template, request, redirect, session, flash, make_response, abort, url_for, jsonify
from flask_mail import Mail, Message
from authlib.integrations.flask_client import OAuth
from twilio.rest import Client as TwilioClient
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import mysql.connector
import jwt
import datetime
import os
import random
import re
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv(override=True)

def validate_password(pw):
    """Return error string or None if password meets all requirements."""
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', pw):
        return "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', pw):
        return "Password must contain at least one lowercase letter."
    if not re.search(r'[0-9]', pw):
        return "Password must contain at least one number."
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};\':",.<>?/\\|`~]', pw):
        return "Password must contain at least one special character (!@#$%…)."
    return None


def normalize_social_url(url):
    """Trim a social/profile link and prefix https:// if no scheme was given."""
    url = (url or "").strip()
    if not url:
        return None
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret")

@app.template_filter('fmt_time')
def fmt_time(t):
    """Format a TIME value (timedelta or time) as 12-hour HH:MM AM/PM."""
    if t is None:
        return '—'
    if hasattr(t, 'strftime'):
        return t.strftime('%I:%M %p')
    # MySQL returns TIME as timedelta
    total = int(t.total_seconds())
    h, m = total // 3600, (total % 3600) // 60
    period = 'AM' if h < 12 else 'PM'
    return f"{h % 12 or 12:02d}:{m:02d} {period}"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

# ─── PROFILE PICTURE UPLOADS ───────────────────────────────────────────────────
PROFILE_PIC_FOLDER = os.path.join(app.root_path, "static", "uploads", "profile_pics")
os.makedirs(PROFILE_PIC_FOLDER, exist_ok=True)
ALLOWED_PIC_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_PROFILE_PIC_BYTES = 3 * 1024 * 1024  # 3 MB

def allowed_pic(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PIC_EXTENSIONS

# ─── MAIL CONFIG ───────────────────────────────────────────────────────────────
app.config["MAIL_SERVER"]   = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"]     = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USE_SSL"]  = False
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")
mail = Mail(app)

# ─── SMS (TWILIO VERIFY) CONFIG ───────────────────────────────────────────────
TWILIO_ACCOUNT_SID        = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN         = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID")
twilio_client = (
    TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
)

def normalize_phone(raw):
    """Return the number in E.164 (+countrycode...) form, defaulting to India (+91)."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("+"):
        return digits
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return "+91" + digits
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    return None

# ─── JWT CONFIG ───────────────────────────────────────────────────────────────
JWT_SECRET    = os.environ.get("JWT_SECRET", "fallback_jwt_secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# ─── GOOGLE OAUTH CONFIG ──────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ─── DATABASE ─────────────────────────────────────────────────────────────────
_DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_NAME", "event_management"),
    port=int(os.environ.get("DB_PORT", 3306)),
)

class _DB:
    """Thin wrapper that auto-reconnects when the connection drops."""
    def __init__(self):
        self._conn = None
        self._cursor = None
        self._connect()

    def _connect(self):
        self._conn   = mysql.connector.connect(**_DB_CONFIG)
        # buffered=True: results are read off the wire immediately on execute(),
        # so the connection never sits with an "unread result" between the
        # execute() call and a later fetchone()/fetchall() — which matters here
        # because _ping() (called before every cursor attribute access) pings
        # the live connection, and conn.ping() fails if a result is unread.
        self._cursor = self._conn.cursor(buffered=True)

    def _ping(self):
        try:
            self._conn.ping(reconnect=True, attempts=3, delay=2)
        except Exception:
            self._connect()

    # Make db.cursor work exactly as before
    def cursor(self):
        self._ping()
        return self._cursor

    # Make db.commit() / db.rollback() work exactly as before
    def commit(self):
        self._ping()
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

db = _DB()

class _CursorProxy:
    """Proxy that forwards every attribute access to the live cursor.
    This means all existing cursor.execute(...) calls work unchanged
    even after the connection is recycled."""
    def __getattr__(self, name):
        return getattr(db.cursor(), name)

cursor = _CursorProxy()

# ─── CREATE TABLES IF MISSING ─────────────────────────────────────────────────
cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        admin_id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        email    VARCHAR(200) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )
""")
cursor.execute("SELECT COUNT(*) FROM admins")
if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO admins (username, email, password) VALUES (%s, %s, %s)",
        ("admin", "rushi.borra07@gmail.com", "admin123"),
    )
db.commit()

# Ensure registration_date column exists with a DEFAULT and backfill NULLs
try:
    cursor.execute("ALTER TABLE registrations ADD COLUMN registration_date DATETIME DEFAULT CURRENT_TIMESTAMP")
    db.commit()
except Exception:
    db.rollback()
try:
    cursor.execute("""
        UPDATE registrations SET registration_date = NOW()
        WHERE registration_date IS NULL
    """)
    db.commit()
except Exception:
    db.rollback()

# Add reminder_sent column to registrations if it doesn't exist yet
try:
    cursor.execute("ALTER TABLE registrations ADD COLUMN reminder_sent TINYINT(1) DEFAULT 0")
    db.commit()
except Exception:
    db.rollback()

# Add notification_email column to registrations if it doesn't exist yet
try:
    cursor.execute("ALTER TABLE registrations ADD COLUMN notification_email VARCHAR(200) NULL")
    db.commit()
except Exception:
    db.rollback()

# Create attendance table if it doesn't exist
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INT AUTO_INCREMENT PRIMARY KEY,
            event_id INT NOT NULL,
            registration_id INT NOT NULL,
            is_present TINYINT(1) DEFAULT 0,
            marked_at TIMESTAMP NULL,
            UNIQUE KEY uq_attendance (event_id, registration_id),
            FOREIGN KEY (event_id) REFERENCES events(event_id),
            FOREIGN KEY (registration_id) REFERENCES registrations(reg_id)
        )
    """)
    db.commit()
except Exception:
    db.rollback()

# Add username column to students if it doesn't exist yet
try:
    cursor.execute("ALTER TABLE students ADD COLUMN username VARCHAR(100) UNIQUE NULL")
    db.commit()
except Exception:
    db.rollback()

# Add student profile columns if they don't exist yet
for _col, _def in [
    ("phone",         "VARCHAR(20)  NULL"),
    ("year",          "VARCHAR(20)  NULL"),
    ("dept",          "VARCHAR(100) NULL"),
    ("section",       "VARCHAR(20)  NULL"),
    ("roll_no",       "VARCHAR(50)  NULL"),
    ("bio",           "TEXT         NULL"),
    ("profile_pic",   "VARCHAR(255) NULL"),
    ("github_url",    "VARCHAR(255) NULL"),
    ("linkedin_url",  "VARCHAR(255) NULL"),
    ("portfolio_url", "VARCHAR(255) NULL"),
    ("instagram_url", "VARCHAR(255) NULL"),
]:
    try:
        cursor.execute(f"ALTER TABLE students ADD COLUMN {_col} {_def}")
        db.commit()
    except Exception:
        db.rollback()

# Create event discussion room table if it doesn't exist
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_discussion_messages (
            message_id  INT AUTO_INCREMENT PRIMARY KEY,
            event_id    INT NOT NULL,
            student_id  INT NULL,
            admin_id    INT NULL,
            message     TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_event_discussion_event (event_id)
        )
    """)
    db.commit()
except Exception:
    db.rollback()

# Create community Q&A tables if they don't exist
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_questions (
            question_id        INT AUTO_INCREMENT PRIMARY KEY,
            student_id          INT NOT NULL,
            title               VARCHAR(255) NOT NULL,
            body                TEXT NOT NULL,
            tags                VARCHAR(255) NULL,
            status              VARCHAR(20) DEFAULT 'open',
            accepted_answer_id  INT NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
except Exception:
    db.rollback()

try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_answers (
            answer_id   INT AUTO_INCREMENT PRIMARY KEY,
            question_id INT NOT NULL,
            student_id  INT NOT NULL,
            body        TEXT NOT NULL,
            flag_count  INT DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_community_answers_question (question_id)
        )
    """)
    db.commit()
except Exception:
    db.rollback()

try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_answer_flags (
            flag_id    INT AUTO_INCREMENT PRIMARY KEY,
            answer_id  INT NOT NULL,
            student_id INT NOT NULL,
            UNIQUE KEY uq_answer_flag (answer_id, student_id)
        )
    """)
    db.commit()
except Exception:
    db.rollback()

# ─── JWT HELPERS ──────────────────────────────────────────────────────────────
def create_jwt(data: dict) -> str:
    payload = {
        **data,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """Read JWT from cookie and return decoded payload, or None."""
    token = request.cookies.get("token")
    if not token:
        return None
    return verify_jwt(token)


def set_jwt_cookie(response, data: dict):
    """Attach a signed JWT cookie to a response."""
    token = create_jwt(data)
    response.set_cookie(
        "token",
        token,
        httponly=True,
        max_age=JWT_EXPIRY_HOURS * 3600,
        samesite="Lax",
    )
    return response


# ─── HOME ─────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return redirect("/select_role")


# ─── REGISTER ─────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form["name"]
        username = request.form["username"].strip()
        email    = request.form["email"]
        password = request.form["password"]

        if not name or not username or not email or not password:
            abort(400)

        pw_error = validate_password(password)
        if pw_error:
            return render_template("register.html", error=pw_error)

        cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
        if cursor.fetchone():
            return render_template("register.html", error="An account with this email already exists. Please login.")

        cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
        if cursor.fetchone():
            return render_template("register.html", error="That username is already taken. Please choose another.")

        otp = str(random.randint(100000, 999999))
        session["pending_registration"] = {
            "name": name,
            "username": username,
            "email": email,
            "password": password,
            "otp": otp,
            "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat(),
        }

        msg = Message("Verify Your Email — Event Bliss", recipients=[email])
        msg.body = (
            f"Hi {name},\n\n"
            f"Thanks for registering on Event Bliss!\n\n"
            f"Your verification OTP is:\n\n"
            f"  {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
            f"If you did not sign up, ignore this email.\n\n"
            f"— Event Bliss Team"
        )
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Registration OTP mail error: {e}")
            session.pop("pending_registration", None)
            return render_template("register.html", error="Failed to send verification email. Please check your email address and try again.")
        flash(f"A 6-digit OTP has been sent to {email}. Please check your inbox. 📧")
        return redirect("/verify_email")

    return render_template("register.html")


# ─── EMAIL OTP VERIFICATION ───────────────────────────────────────────────────
@app.route("/verify_email", methods=["GET", "POST"])
def verify_email():
    pending = session.get("pending_registration")
    if not pending:
        flash("No pending registration. Please register first.")
        return redirect("/register")

    if request.method == "POST":
        entered_otp = request.form["otp"].strip()
        expires_at  = datetime.datetime.fromisoformat(pending["expires_at"])

        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            session.pop("pending_registration", None)
            flash("OTP expired. Please register again. ⏰")
            return redirect("/register")

        if entered_otp != pending["otp"]:
            flash("Incorrect OTP. Please try again. ❌")
            return render_template("verify_email.html", email=pending["email"])

        cursor.execute("SELECT * FROM students WHERE email = %s", (pending["email"],))
        if cursor.fetchone():
            session.pop("pending_registration", None)
            flash("Account already exists. Please login. 💌")
            return redirect("/student_login")

        cursor.execute(
            "INSERT INTO students (name, username, email, password) VALUES (%s, %s, %s, %s)",
            (pending["name"], pending.get("username"), pending["email"], pending["password"]),
        )
        db.commit()
        session.pop("pending_registration", None)
        flash("Email verified! Your account has been created. 🎉")
        return redirect("/student_login")

    return render_template("verify_email.html", email=pending["email"])


# ─── SELECT ROLE ──────────────────────────────────────────────────────────────
@app.route("/select_role")
def select_role():
    return render_template("select_role.html")


# ─── STUDENT LOGIN (email/password) ───────────────────────────────────────────
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        username_or_email = request.form["username"].strip()
        password          = request.form["password"]

        # Try username first, then email
        cursor.execute("SELECT * FROM students WHERE (username=%s OR email=%s) AND password=%s",
                       (username_or_email, username_or_email, password))
        user = cursor.fetchone()

        if user:
            response = make_response(redirect("/dashboard"))
            set_jwt_cookie(response, {
                "user_id":   user[0],
                "user_name": user[1],
                "role":      "student",
            })
            return response
        else:
            return render_template("student_login.html", error="Invalid username/email or password. Please try again.")

    return render_template("student_login.html")


# ─── GOOGLE OAUTH ─────────────────────────────────────────────────────────────
@app.route("/google_login")
def google_login():
    redirect_uri = "http://127.0.0.1:5000/google_callback"
    return google.authorize_redirect(redirect_uri)


@app.route("/google_callback")
def google_callback():
    token      = google.authorize_access_token()
    user_info  = token.get("userinfo")
    email      = user_info["email"]
    name       = user_info["name"]

    # Find or auto-create the student
    cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO students (name, email, password) VALUES (%s, %s, %s)",
            (name, email, "GOOGLE_OAUTH"),
        )
        db.commit()
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        user = cursor.fetchone()

    # Google has already verified this email address, so log the student
    # straight into their dashboard — no extra OTP step needed.
    response = make_response(redirect("/dashboard"))
    set_jwt_cookie(response, {
        "user_id":   user[0],
        "user_name": user[1],
        "role":      "student",
    })
    return response


# ─── ADMIN LOGIN ──────────────────────────────────────────────────────────────
@app.route("/admin_login", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM admins WHERE username=%s AND password=%s", (username, password))
        admin_user = cursor.fetchone()

        if admin_user:
            response = make_response(redirect("/admin_dashboard"))
            set_jwt_cookie(response, {"role": "admin", "admin_id": admin_user[0], "admin_username": admin_user[1]})
            return response
        else:
            return render_template("admin.html", error="Invalid credentials. Please check your username and password.")

    return render_template("admin.html")


# ─── ADMIN EMAIL OTP LOGIN ─────────────────────────────────────────────────────
@app.route("/admin_email_otp", methods=["POST"])
def admin_email_otp():
    email = (request.form.get("admin_otp_email") or "").strip()
    if not email or "@" not in email:
        return render_template("admin.html", otp_error="Please enter a valid email address.")
    cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
    admin_user = cursor.fetchone()
    if not admin_user:
        return render_template("admin.html", otp_error="No admin account found with that email.")
    otp = str(random.randint(100000, 999999))
    session["admin_email_login_otp"] = {
        "admin_id":       admin_user[0],
        "admin_username": admin_user[1],
        "email":          email,
        "otp":            otp,
        "expires_at":     (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat(),
    }
    try:
        msg = Message("Admin Login OTP — Event Bliss", recipients=[email])
        msg.body = (
            f"Hi {admin_user[1]},\n\n"
            f"Your one-time login OTP for Event Bliss Admin is:\n\n"
            f"  {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it.\n\n"
            f"If you did not attempt to log in, ignore this email.\n\n"
            f"— Event Bliss Team"
        )
        mail.send(msg)
        flash(f"OTP sent to {email}. Enter it below to login. 📧")
        return redirect("/verify_admin_email_otp")
    except Exception as e:
        app.logger.error(f"Admin email OTP login error: {e}")
        return render_template("admin.html", otp_error="Failed to send OTP. Please try again.")


@app.route("/verify_admin_email_otp", methods=["GET", "POST"])
def verify_admin_email_otp():
    pending = session.get("admin_email_login_otp")
    if not pending:
        flash("No pending OTP login. Please try again.")
        return redirect("/admin_login")

    if request.method == "POST":
        entered_otp = request.form["otp"].strip()
        expires_at  = datetime.datetime.fromisoformat(pending["expires_at"])

        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            session.pop("admin_email_login_otp", None)
            flash("OTP expired. Please try again. ⏰")
            return redirect("/admin_login")

        if entered_otp != pending["otp"]:
            return render_template("verify_admin_email_otp.html",
                                   email=pending["email"], error="Incorrect OTP. Please try again.")

        session.pop("admin_email_login_otp", None)
        response = make_response(redirect("/admin_dashboard"))
        set_jwt_cookie(response, {
            "role":           "admin",
            "admin_id":       pending["admin_id"],
            "admin_username": pending["admin_username"],
        })
        return response

    return render_template("verify_admin_email_otp.html", email=pending["email"])


# legacy alias kept so old links still work
@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.args.get("role", "")
    if role == "admin":
        return redirect("/admin_login")
    return redirect("/student_login")


# ─── LOGOUT ───────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()          # clear reset_email if present
    response = make_response(redirect("/"))
    response.delete_cookie("token")
    return response


# ─── STUDENT DASHBOARD ────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")
    return render_template("dashboard.html", name=user["user_name"])


# ─── PERMISSIONS HELPER ───────────────────────────────────────────────────────
def get_admin_permissions(username="admin"):
    cursor.execute("SELECT * FROM permissions WHERE admin_username=%s", (username,))
    row = cursor.fetchone()
    if not row:
        return {"can_create_event": False, "can_delete_event": False,
                "can_edit_event": False, "can_view_registrations": False}
    return {
        "can_create_event":        bool(row[2]),
        "can_delete_event":        bool(row[3]),
        "can_edit_event":          bool(row[4]),
        "can_view_registrations":  bool(row[5]),
    }


# ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────
@app.route("/admin_dashboard")
def admin_dashboard():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registrations")
    total_registrations = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM venues")
    total_venues = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rsvps")
    total_rsvps = cursor.fetchone()[0]

    perms = get_admin_permissions()

    return render_template(
        "admin_dashboard.html",
        total_events=total_events,
        total_students=total_students,
        total_registrations=total_registrations,
        total_venues=total_venues,
        total_rsvps=total_rsvps,
        perms=perms,
    )


# ─── ANALYTICS DASHBOARD ──────────────────────────────────────────────────────
@app.route("/analytics")
def analytics():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    import json as _json

    def q(sql, params=()):
        cursor.execute(sql, params)
        return cursor.fetchall()

    # ── Top events by registrations ──────────────────────────────────────────
    top_events = q("""
        SELECT e.event_name, COUNT(r.reg_id) AS cnt
        FROM events e
        LEFT JOIN registrations r ON e.event_id = r.event_id
        GROUP BY e.event_id, e.event_name
        ORDER BY cnt DESC
        LIMIT 8
    """)

    # ── Department breakdown ──────────────────────────────────────────────────
    dept_data = q("""
        SELECT dept, COUNT(*) AS cnt
        FROM registrations
        WHERE dept IS NOT NULL AND dept != ''
        GROUP BY dept
        ORDER BY cnt DESC
        LIMIT 8
    """)

    # ── Year-wise distribution ────────────────────────────────────────────────
    year_data = q("""
        SELECT year, COUNT(*) AS cnt
        FROM registrations
        WHERE year IS NOT NULL AND year != ''
        GROUP BY year
        ORDER BY cnt DESC
    """)

    # ── Monthly registration trend (last 12 months) ───────────────────────────
    import calendar as _cal
    monthly_raw = q("""
        SELECT DATE_FORMAT(registration_date, '%Y-%m') AS ym,
               COUNT(*) AS cnt
        FROM registrations
        WHERE registration_date IS NOT NULL
        GROUP BY DATE_FORMAT(registration_date, '%Y-%m')
        ORDER BY ym DESC
        LIMIT 12
    """)
    monthly_raw = list(reversed(monthly_raw))   # oldest → newest
    def _ym_label(ym):
        if not ym:
            return 'Unknown'
        parts = ym.split('-')
        if len(parts) != 2:
            return ym
        return f"{_cal.month_abbr[int(parts[1])]} {parts[0]}"
    monthly_data = [(_ym_label(r[0]), r[1]) for r in monthly_raw]

    # ── Venue usage ───────────────────────────────────────────────────────────
    venue_data = q("""
        SELECT COALESCE(v.venue_name, e.venue, 'Unknown') AS venue,
               COUNT(r.reg_id) AS cnt
        FROM registrations r
        JOIN events e ON r.event_id = e.event_id
        LEFT JOIN venues v ON e.venue_id = v.venue_id
        GROUP BY COALESCE(v.venue_name, e.venue, 'Unknown')
        ORDER BY cnt DESC
        LIMIT 6
    """)

    # ── Section distribution ──────────────────────────────────────────────────
    section_data = q("""
        SELECT section, COUNT(*) AS cnt
        FROM registrations
        WHERE section IS NOT NULL AND section != ''
        GROUP BY section
        ORDER BY cnt DESC
        LIMIT 8
    """)

    # ── Upcoming vs past events ───────────────────────────────────────────────
    upcoming = q("SELECT COUNT(*) FROM events WHERE event_date >= CURDATE()")[0][0]
    past     = q("SELECT COUNT(*) FROM events WHERE event_date < CURDATE()")[0][0]

    # ── Avg registrations per event ───────────────────────────────────────────
    avg_row = q("SELECT ROUND(AVG(cnt),1) FROM (SELECT COUNT(*) cnt FROM registrations GROUP BY event_id) t")
    avg_regs = avg_row[0][0] or 0

    # ── Most recent 5 registrations ───────────────────────────────────────────
    recent_regs_raw = q("""
        SELECT CONCAT_WS(' ', r.first_name, r.last_name) AS student_name,
               e.event_name,
               COALESCE(r.dept, '—') AS dept,
               DATE_FORMAT(r.registration_date, '%d %b %Y') AS reg_date
        FROM registrations r
        JOIN events e ON r.event_id = e.event_id
        WHERE r.registration_date IS NOT NULL
        ORDER BY r.registration_date DESC
        LIMIT 5
    """)
    recent_regs = [(r[0] or '—', r[1], r[2], r[3]) for r in recent_regs_raw]

    def to_json(rows):
        return _json.dumps([list(r) for r in rows])

    return render_template(
        "analytics.html",
        top_events=to_json(top_events),
        dept_data=to_json(dept_data),
        year_data=to_json(year_data),
        monthly_data=to_json(monthly_data),
        venue_data=to_json(venue_data),
        section_data=to_json(section_data),
        upcoming=upcoming, past=past,
        avg_regs=avg_regs,
        recent_regs=recent_regs,
        total_events=upcoming + past,
    )


# ─── ADMIN EVENTS ─────────────────────────────────────────────────────────────
@app.route("/admin_events")
def admin_events():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    # Upcoming events
    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date, events.event_time,
               COALESCE(venues.venue_name, events.venue) AS venue_display,
               events.max_seats, events.organiser
        FROM events
        LEFT JOIN venues ON events.venue_id = venues.venue_id
        WHERE events.event_date >= CURDATE()
        ORDER BY events.event_date ASC, events.event_time ASC
    """)
    upcoming_events = cursor.fetchall()

    # Completed (past) events with registration + attendance counts via subqueries
    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date, events.event_time,
               COALESCE(venues.venue_name, events.venue) AS venue_display,
               events.max_seats, events.organiser,
               (SELECT COUNT(*) FROM registrations WHERE registrations.event_id = events.event_id) AS registered,
               (SELECT COUNT(*) FROM attendance WHERE attendance.event_id = events.event_id AND attendance.is_present = 1) AS attended
        FROM events
        LEFT JOIN venues ON events.venue_id = venues.venue_id
        WHERE events.event_date < CURDATE()
        ORDER BY events.event_date DESC
    """)
    completed_events = cursor.fetchall()

    perms = get_admin_permissions()
    return render_template("admin_events.html", upcoming_events=upcoming_events,
                           completed_events=completed_events, perms=perms)


# ─── ATTENDANCE TRACKER ───────────────────────────────────────────────────────
@app.route("/admin_attendance/<int:event_id>", methods=["GET", "POST"])
def admin_attendance(event_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    if request.method == "POST":
        present_ids = set(request.form.getlist("present"))
        cursor.execute("SELECT reg_id FROM registrations WHERE event_id=%s", (event_id,))
        all_reg_ids = [r[0] for r in cursor.fetchall()]
        for reg_id in all_reg_ids:
            is_present = 1 if str(reg_id) in present_ids else 0
            cursor.execute("""
                INSERT INTO attendance (event_id, registration_id, is_present, marked_at)
                VALUES (%s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE is_present=%s, marked_at=NOW()
            """, (event_id, reg_id, is_present, is_present))
        db.commit()
        flash("Attendance saved successfully! ✅")
        return redirect("/admin_events?tab=completed")

    cursor.execute("""
        SELECT events.event_name, events.event_date, events.event_time,
               COALESCE(venues.venue_name, events.venue)
        FROM events
        LEFT JOIN venues ON events.venue_id = venues.venue_id
        WHERE events.event_id = %s
    """, (event_id,))
    event = cursor.fetchone()

    cursor.execute("""
        SELECT r.reg_id,
               CONCAT(r.first_name, ' ', COALESCE(r.middle_name,''), ' ', r.last_name) AS full_name,
               r.roll_no, r.dept, r.section, r.year,
               COALESCE(a.is_present, 0) AS is_present
        FROM registrations r
        LEFT JOIN attendance a ON r.reg_id = a.registration_id AND a.event_id = %s
        WHERE r.event_id = %s
        ORDER BY r.roll_no
    """, (event_id, event_id))
    students = cursor.fetchall()

    present_count = sum(1 for s in students if s[6])
    return render_template("attendance.html", event=event, event_id=event_id,
                           students=students, present_count=present_count,
                           total=len(students))


# ─── CREATE EVENT ─────────────────────────────────────────────────────────────
@app.route("/create_event", methods=["GET", "POST"])
def create_event():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    perms = get_admin_permissions()
    if not perms["can_create_event"]:
        abort(403)

    if request.method == "POST":
        event_name   = request.form["event_name"]
        event_date   = request.form["event_date"]
        venue_id     = request.form["venue_id"] or None
        max_seats    = request.form["max_seats"]
        event_time   = request.form["event_time"]
        theme        = request.form["theme"]
        requirements = request.form["requirements"]
        organiser    = request.form["organiser"]

        cursor.execute("""
            INSERT INTO events (event_name, event_date, event_time, venue_id, max_seats, theme, requirements, organiser)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (event_name, event_date, event_time, venue_id, max_seats, theme, requirements, organiser))
        db.commit()

        return render_template("event_created.html")

    cursor.execute("SELECT venue_id, venue_name, location, capacity FROM venues ORDER BY venue_name")
    venues = cursor.fetchall()
    return render_template("create_event.html", venues=venues)


# ─── AVAILABLE VENUES API ─────────────────────────────────────────────────────
@app.route("/available_venues")
def available_venues():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401

    date     = request.args.get("date")
    time_slot = request.args.get("slot")   # "morning" or "afternoon"

    cursor.execute("SELECT venue_id, venue_name, location, capacity FROM venues ORDER BY venue_name")
    all_venues = cursor.fetchall()

    booked_ids = set()
    if date and time_slot:
        if time_slot == "morning":
            cursor.execute("""
                SELECT DISTINCT venue_id FROM events
                WHERE event_date = %s AND venue_id IS NOT NULL
                  AND TIME(COALESCE(event_time, '00:00:00')) < '12:00:00'
            """, (date,))
        else:
            cursor.execute("""
                SELECT DISTINCT venue_id FROM events
                WHERE event_date = %s AND venue_id IS NOT NULL
                  AND TIME(COALESCE(event_time, '00:00:00')) >= '12:00:00'
            """, (date,))
        booked_ids = {r[0] for r in cursor.fetchall()}

    return jsonify([
        {
            "id":        v[0],
            "name":      v[1],
            "location":  v[2],
            "capacity":  v[3],
            "available": v[0] not in booked_ids,
        }
        for v in all_venues
    ])


# ─── EVENTS (student view) ────────────────────────────────────────────────────
@app.route("/events")
def events():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    user_id = user["user_id"]

    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date,
               COALESCE(venues.venue_name, events.venue) AS venue_display,
               events.max_seats,
               COUNT(registrations.event_id) AS registered,
               events.event_time
        FROM events
        LEFT JOIN registrations ON events.event_id = registrations.event_id
        LEFT JOIN venues ON events.venue_id = venues.venue_id
        WHERE events.event_date >= CURDATE()
        GROUP BY events.event_id
        ORDER BY events.event_date ASC, events.event_time ASC
    """)
    all_events = cursor.fetchall()

    cursor.execute("SELECT event_id FROM registrations WHERE student_id=%s", (user_id,))
    registered_events = [r[0] for r in cursor.fetchall()]

    return render_template("events.html", events=all_events, registered_events=registered_events)


# ─── NOTIFICATION EMAIL OTP (AJAX) ────────────────────────────────────────────
@app.route("/send_notification_otp", methods=["POST"])
def send_notification_otp():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email address"})
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
    session["notif_otp"] = otp
    session["notif_otp_email"] = email
    session["notif_otp_expiry"] = expiry
    try:
        msg = Message("Event Notification Email Verification — Event Bliss", recipients=[email])
        msg.body = (
            f"Hi,\n\n"
            f"Your OTP to verify this email for event notifications is:\n\n"
            f"  {otp}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"— Event Bliss Team"
        )
        mail.send(msg)
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.error(f"Notification OTP mail error: {e}")
        return jsonify({"ok": False, "error": "Could not send email. Check the address."})


@app.route("/verify_notification_otp", methods=["POST"])
def verify_notification_otp():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    entered = (data.get("otp") or "").strip()
    stored_otp    = session.get("notif_otp")
    stored_email  = session.get("notif_otp_email")
    stored_expiry = session.get("notif_otp_expiry")
    if not stored_otp or not stored_email or not stored_expiry:
        return jsonify({"ok": False, "error": "No OTP session. Please resend."})
    if datetime.datetime.now(datetime.timezone.utc) > datetime.datetime.fromisoformat(stored_expiry):
        return jsonify({"ok": False, "error": "OTP expired. Please resend."})
    if entered != stored_otp:
        return jsonify({"ok": False, "error": "Incorrect OTP."})
    # Clear OTP session keys
    session.pop("notif_otp", None)
    session.pop("notif_otp_expiry", None)
    return jsonify({"ok": True, "email": stored_email})


# ─── REGISTER FOR EVENT ───────────────────────────────────────────────────────
@app.route("/register_event/<int:event_id>", methods=["GET", "POST"])
def register_event(event_id):
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    student_id = user["user_id"]

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.execute("SELECT email FROM students WHERE student_id=%s", (student_id,))
    s_row = cursor.fetchone()
    student_email = s_row[0] if s_row else ""

    if request.method == "POST":
        first_name        = request.form.get("first_name")
        middle_name       = request.form.get("middle_name")
        last_name         = request.form.get("last_name")
        year              = request.form.get("year")
        dept              = request.form.get("dept")
        section           = request.form.get("section")
        roll_no           = request.form.get("roll_no")
        phone             = request.form.get("phone")
        notification_email = (request.form.get("notification_email") or "").strip() or None

        missing_fields = [
            f for f, v in [
                ("first_name", first_name), ("last_name", last_name),
                ("year", year), ("dept", dept), ("section", section),
                ("roll_no", roll_no), ("phone", phone),
            ] if not v
        ]

        if missing_fields:
            flash("⚠ Please fill all required fields")
            return render_template(
                "event_registration_form.html",
                event=event,
                form_data=request.form,
                missing_fields=missing_fields,
                student_email=student_email,
            )

        cursor.execute(
            "SELECT * FROM registrations WHERE student_id=%s AND event_id=%s",
            (student_id, event_id),
        )
        if cursor.fetchone():
            abort(409)

        cursor.execute("""
            INSERT INTO registrations
            (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone, notification_email, registration_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone, notification_email))
        db.commit()

        # ── Registration confirmation email ───────────────────────────────────
        try:
            cursor.execute("SELECT email, name FROM students WHERE student_id=%s", (student_id,))
            s_info = cursor.fetchone()
            if s_info:
                conf_email = (notification_email or s_info[0] or "").strip()
                if not conf_email:
                    raise ValueError("No valid email address found for registration confirmation")
                venue_display = event[3]
                if event[8]:
                    cursor.execute("SELECT venue_name FROM venues WHERE venue_id=%s", (event[8],))
                    v_row = cursor.fetchone()
                    if v_row:
                        venue_display = v_row[0]
                msg = Message("Registration Successful — Event Bliss", recipients=[conf_email])
                msg.body = (
                    f"Hi {first_name or s_info[1]},\n\n"
                    f"You have successfully registered for the following event:\n\n"
                    f"  Event  : {event[1]}\n"
                    f"  Date   : {event[2]}\n"
                    f"  Time   : {_fmt_time(event[5])}\n"
                    f"  Venue  : {venue_display or 'TBD'}\n\n"
                    f"We look forward to seeing you there!\n\n"
                    f"— Event Bliss Team"
                )
                mail.send(msg)
        except Exception as conf_err:
            app.logger.error(f"Registration confirmation email error: {conf_err}")

        # Immediate reminder if event is within the next 24 hours
        try:
            ev_date = event[2]   # datetime.date
            ev_time = event[5]   # datetime.timedelta or None
            if ev_date and ev_time is not None:
                if isinstance(ev_time, datetime.timedelta):
                    event_dt = datetime.datetime.combine(ev_date, datetime.time()) + ev_time
                else:
                    event_dt = datetime.datetime.combine(ev_date, ev_time)
                time_until = event_dt - datetime.datetime.now()
                if datetime.timedelta(0) < time_until <= datetime.timedelta(hours=24):
                    cursor.execute("SELECT email, name FROM students WHERE student_id=%s", (student_id,))
                    s_row = cursor.fetchone()
                    if s_row:
                        venue_display = event[3]
                        if event[8]:
                            cursor.execute("SELECT venue_name FROM venues WHERE venue_id=%s", (event[8],))
                            v_row = cursor.fetchone()
                            if v_row:
                                venue_display = v_row[0]
                        msg = Message("Event Reminder — Event Bliss", recipients=[s_row[0]])
                        msg.body = (
                            f"Hi {first_name or s_row[1]},\n\n"
                            f"You just registered for an event starting in less than 24 hours!\n\n"
                            f"  Event  : {event[1]}\n"
                            f"  Date   : {ev_date}\n"
                            f"  Time   : {_fmt_time(ev_time)}\n"
                            f"  Venue  : {venue_display or 'TBD'}\n\n"
                            f"See you there!\n\n"
                            f"— Event Bliss Team"
                        )
                        mail.send(msg)
                        cursor.execute(
                            "UPDATE registrations SET reminder_sent = 1 WHERE student_id=%s AND event_id=%s",
                            (student_id, event_id),
                        )
                        db.commit()
        except Exception as reminder_err:
            app.logger.error(f"Immediate reminder error: {reminder_err}")

        session["reg_success_event"] = event[1]
        return redirect("/registration_success")

    return render_template("event_registration_form.html", event=event, student_email=student_email)


# ─── REGISTRATION SUCCESS ─────────────────────────────────────────────────────
@app.route("/registration_success")
def registration_success():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")
    event_name = session.pop("reg_success_event", "the event")
    return render_template("registration_success.html", event_name=event_name, name=user["user_name"])


# ─── MY EVENTS ────────────────────────────────────────────────────────────────
@app.route("/my_events")
def my_events():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date, events.event_time, events.venue,
               a.is_present
        FROM registrations
        JOIN events ON registrations.event_id = events.event_id
        LEFT JOIN attendance a ON a.registration_id = registrations.reg_id
                               AND a.event_id = events.event_id
        WHERE registrations.student_id = %s
        ORDER BY events.event_date DESC, events.event_time DESC
    """, (user["user_id"],))

    now = datetime.datetime.now()
    events = []
    for row in cursor.fetchall():
        event_id, name, date, time_val, venue, is_present = row
        # Build event datetime for comparison
        if date and time_val:
            if isinstance(time_val, datetime.timedelta):
                event_dt = datetime.datetime.combine(date, (datetime.datetime.min + time_val).time())
            else:
                event_dt = datetime.datetime.combine(date, time_val)
            completed = event_dt < now
        elif date:
            completed = date < now.date()
        else:
            completed = False
        # attendance: None = not marked yet, 1 = attended, 0 = absent
        events.append((event_id, name, date, venue, completed, is_present))

    return render_template("my_events.html", events=events)


# ─── STUDENT PROFILE ──────────────────────────────────────────────────────────
@app.route("/student_profile", methods=["GET", "POST"])
def student_profile():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    student_id = user["user_id"]

    if request.method == "POST":
        name       = request.form.get("name", "").strip()
        year       = request.form.get("year", "").strip()
        dept       = request.form.get("dept", "").strip()
        section    = request.form.get("section", "").strip()
        roll_no    = request.form.get("roll_no", "").strip()
        bio        = request.form.get("bio", "").strip()
        github_url    = normalize_social_url(request.form.get("github_url"))
        linkedin_url  = normalize_social_url(request.form.get("linkedin_url"))
        portfolio_url = normalize_social_url(request.form.get("portfolio_url"))
        instagram_url = normalize_social_url(request.form.get("instagram_url"))

        if not name:
            flash("⚠ Name cannot be empty.")
        else:
            profile_pic_file = request.files.get("profile_pic")
            pic_filename = None
            if profile_pic_file and profile_pic_file.filename:
                if not allowed_pic(profile_pic_file.filename):
                    flash("⚠ Profile picture must be a PNG, JPG, GIF or WEBP image.")
                    return redirect("/student_profile")
                profile_pic_file.seek(0, os.SEEK_END)
                if profile_pic_file.tell() > MAX_PROFILE_PIC_BYTES:
                    flash("⚠ Profile picture must be under 3 MB.")
                    return redirect("/student_profile")
                profile_pic_file.seek(0)
                ext = profile_pic_file.filename.rsplit(".", 1)[1].lower()
                pic_filename = secure_filename(f"student_{student_id}.{ext}")
                profile_pic_file.save(os.path.join(PROFILE_PIC_FOLDER, pic_filename))

            if pic_filename:
                cursor.execute("""
                    UPDATE students
                    SET name=%s, year=%s, dept=%s, section=%s, roll_no=%s, bio=%s,
                        github_url=%s, linkedin_url=%s, portfolio_url=%s, instagram_url=%s,
                        profile_pic=%s
                    WHERE student_id=%s
                """, (name, year or None, dept or None,
                      section or None, roll_no or None, bio or None,
                      github_url, linkedin_url, portfolio_url, instagram_url,
                      pic_filename, student_id))
            else:
                cursor.execute("""
                    UPDATE students
                    SET name=%s, year=%s, dept=%s, section=%s, roll_no=%s, bio=%s,
                        github_url=%s, linkedin_url=%s, portfolio_url=%s, instagram_url=%s
                    WHERE student_id=%s
                """, (name, year or None, dept or None,
                      section or None, roll_no or None, bio or None,
                      github_url, linkedin_url, portfolio_url, instagram_url,
                      student_id))
            db.commit()
            flash("✅ Profile updated successfully!")

    cursor.execute("""
        SELECT name, email, phone, year, dept, section, roll_no, bio,
               profile_pic, github_url, linkedin_url, portfolio_url, instagram_url
        FROM students WHERE student_id=%s
    """, (student_id,))
    row = cursor.fetchone()
    student = {
        "name":    row[0], "email":   row[1], "phone":   row[2],
        "year":    row[3], "dept":    row[4], "section": row[5],
        "roll_no": row[6], "bio":     row[7],
        "profile_pic":   row[8],
        "github_url":    row[9],
        "linkedin_url":  row[10],
        "portfolio_url": row[11],
        "instagram_url": row[12],
    }

    # Count registered events
    cursor.execute("SELECT COUNT(*) FROM registrations WHERE student_id=%s", (student_id,))
    event_count = cursor.fetchone()[0]

    return render_template("student_profile.html", student=student, event_count=event_count)


# ─── EMAIL CHANGE OTP ─────────────────────────────────────────────────────────
@app.route("/send_email_change_otp", methods=["POST"])
def send_email_change_otp():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    new_email = (data.get("new_email") or "").strip().lower()
    if not new_email or "@" not in new_email:
        return jsonify({"ok": False, "error": "Invalid email address."})
    cursor.execute("SELECT student_id FROM students WHERE email=%s", (new_email,))
    if cursor.fetchone():
        return jsonify({"ok": False, "error": "This email is already in use by another account."})
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
    session["email_change_otp"] = {"new_email": new_email, "otp": otp, "expires_at": expiry}
    try:
        msg = Message("Verify Your New Email — Event Bliss", recipients=[new_email])
        msg.body = (
            f"Hi,\n\n"
            f"You requested to change your email on Event Bliss.\n\n"
            f"Your verification OTP is:\n\n"
            f"  {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it.\n\n"
            f"If you did not request this, ignore this email.\n\n"
            f"— Event Bliss Team"
        )
        mail.send(msg)
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.error(f"Email change OTP error: {e}")
        return jsonify({"ok": False, "error": "Could not send email. Check the address."})


@app.route("/verify_email_change", methods=["POST"])
def verify_email_change():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    entered = (data.get("otp") or "").strip()
    pending = session.get("email_change_otp")
    if not pending:
        return jsonify({"ok": False, "error": "No OTP session. Please resend."})
    if datetime.datetime.now(datetime.timezone.utc) > datetime.datetime.fromisoformat(pending["expires_at"]):
        session.pop("email_change_otp", None)
        return jsonify({"ok": False, "error": "OTP expired. Please resend."})
    if entered != pending["otp"]:
        return jsonify({"ok": False, "error": "Incorrect OTP."})
    cursor.execute("UPDATE students SET email=%s WHERE student_id=%s", (pending["new_email"], user["user_id"]))
    db.commit()
    session.pop("email_change_otp", None)
    return jsonify({"ok": True, "new_email": pending["new_email"]})


# ─── PHONE CHANGE VERIFICATION (TWILIO VERIFY, EMAIL FALLBACK) ────────────────
def _send_phone_change_code(new_phone, student_id):
    """Try SMS via Twilio Verify; fall back to emailing an OTP to the student's
    registered address. Stores pending state in the session and returns
    (ok, channel_or_error)."""
    if twilio_client and TWILIO_VERIFY_SERVICE_SID:
        try:
            twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(
                to=new_phone, channel="sms"
            )
            session["phone_change_pending"] = {"phone": new_phone, "channel": "sms"}
            return True, "sms"
        except Exception as e:
            app.logger.warning(f"Phone change SMS failed, falling back to email: {e}")

    cursor.execute("SELECT email FROM students WHERE student_id=%s", (student_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return False, "Could not send the OTP by SMS or email. Please try again later."
    email = row[0]
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
    try:
        msg = Message("Verify Phone Number Change — Event Bliss", recipients=[email])
        msg.body = (
            f"Hi,\n\n"
            f"You requested to change your phone number to {new_phone} on Event Bliss.\n\n"
            f"Your verification OTP is:\n\n"
            f"  {otp}\n\n"
            f"This OTP is valid for 10 minutes. Do not share it.\n\n"
            f"If you did not request this, ignore this email.\n\n"
            f"— Event Bliss Team"
        )
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Phone change email OTP error: {e}")
        return False, "Could not send the OTP by SMS or email. Please try again later."
    session["phone_change_pending"] = {
        "phone": new_phone, "channel": "email", "email": email,
        "otp": otp, "expires_at": expiry,
    }
    return True, "email"


@app.route("/send_phone_change_otp", methods=["POST"])
def send_phone_change_otp():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    new_phone = normalize_phone(data.get("new_phone"))
    if not new_phone:
        return jsonify({"ok": False, "error": "Please enter a valid phone number (10 digits, or with country code)."})
    ok, result = _send_phone_change_code(new_phone, user["user_id"])
    if not ok:
        return jsonify({"ok": False, "error": result})
    pending = session["phone_change_pending"]
    sent_to = new_phone if result == "sms" else pending["email"]
    return jsonify({"ok": True, "channel": result, "sent_to": sent_to})


@app.route("/resend_phone_change_otp", methods=["POST"])
def resend_phone_change_otp():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    pending = session.get("phone_change_pending")
    if not pending:
        return jsonify({"ok": False, "error": "No pending phone change. Please start again."})
    ok, result = _send_phone_change_code(pending["phone"], user["user_id"])
    if not ok:
        return jsonify({"ok": False, "error": result})
    new_pending = session["phone_change_pending"]
    sent_to = pending["phone"] if result == "sms" else new_pending["email"]
    return jsonify({"ok": True, "channel": result, "sent_to": sent_to})


@app.route("/verify_phone_change", methods=["POST"])
def verify_phone_change():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    entered = (data.get("otp") or "").strip()
    pending = session.get("phone_change_pending")
    if not pending:
        return jsonify({"ok": False, "error": "No OTP session. Please resend."})
    if not entered:
        return jsonify({"ok": False, "error": "Please enter the OTP."})

    if pending["channel"] == "sms":
        try:
            check = twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verification_checks.create(
                to=pending["phone"], code=entered
            )
        except Exception as e:
            app.logger.error(f"Phone change OTP check error: {e}")
            return jsonify({"ok": False, "error": "OTP expired or too many attempts. Please resend."})
        if check.status != "approved":
            return jsonify({"ok": False, "error": "Incorrect OTP."})
    else:
        if datetime.datetime.now(datetime.timezone.utc) > datetime.datetime.fromisoformat(pending["expires_at"]):
            session.pop("phone_change_pending", None)
            return jsonify({"ok": False, "error": "OTP expired. Please resend."})
        if entered != pending["otp"]:
            return jsonify({"ok": False, "error": "Incorrect OTP."})

    # Verified — but don't save yet; the number is written only when the
    # student confirms with the Done button.
    session.pop("phone_change_pending", None)
    session["phone_change_verified"] = pending["phone"]
    return jsonify({"ok": True, "new_phone": pending["phone"]})


@app.route("/confirm_phone_change", methods=["POST"])
def confirm_phone_change():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    verified_phone = session.get("phone_change_verified")
    if not verified_phone:
        return jsonify({"ok": False, "error": "No verified phone number to save. Please verify again."})
    cursor.execute("UPDATE students SET phone=%s WHERE student_id=%s", (verified_phone, user["user_id"]))
    db.commit()
    session.pop("phone_change_verified", None)
    return jsonify({"ok": True, "new_phone": verified_phone})


# ─── SHARED IDENTITY HELPER (used by discussion room + community) ────────────
def get_student_identity(student_id):
    cursor.execute("""
        SELECT name, profile_pic, github_url, linkedin_url, portfolio_url, instagram_url
        FROM students WHERE student_id=%s
    """, (student_id,))
    row = cursor.fetchone()
    if not row:
        return {"name": "Deleted User", "profile_pic": None, "github_url": None,
                "linkedin_url": None, "portfolio_url": None, "instagram_url": None, "is_admin": False}
    return {
        "name": row[0], "profile_pic": row[1], "github_url": row[2],
        "linkedin_url": row[3], "portfolio_url": row[4], "instagram_url": row[5],
        "is_admin": False,
    }


def get_admin_identity(admin_id):
    cursor.execute("SELECT username FROM admins WHERE admin_id=%s", (admin_id,))
    row = cursor.fetchone()
    return {
        "name": row[0] if row else "Admin", "profile_pic": None, "github_url": None,
        "linkedin_url": None, "portfolio_url": None, "instagram_url": None, "is_admin": True,
    }


# ─── EVENT DISCUSSION ROOM ─────────────────────────────────────────────────────
def _can_access_discussion(event_id, user):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    if user.get("role") == "student":
        cursor.execute(
            "SELECT 1 FROM registrations WHERE student_id=%s AND event_id=%s",
            (user["user_id"], event_id)
        )
        return cursor.fetchone() is not None
    return False


@app.route("/event/<int:event_id>/discussion")
def event_discussion(event_id):
    user = get_current_user()
    if not user:
        return redirect("/student_login")
    if not _can_access_discussion(event_id, user):
        flash("⚠ You need to be registered for this event to join its discussion room.")
        return redirect("/my_events")

    cursor.execute("SELECT event_id, event_name FROM events WHERE event_id=%s", (event_id,))
    event_row = cursor.fetchone()
    if not event_row:
        abort(404)

    return render_template(
        "event_discussion.html",
        event={"event_id": event_row[0], "event_name": event_row[1]},
        is_admin=(user.get("role") == "admin"),
    )


@app.route("/event/<int:event_id>/discussion/messages")
def event_discussion_messages(event_id):
    user = get_current_user()
    if not _can_access_discussion(event_id, user):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    after = request.args.get("after", 0, type=int)
    cursor.execute("""
        SELECT message_id, student_id, admin_id, message, created_at
        FROM event_discussion_messages
        WHERE event_id=%s AND message_id > %s
        ORDER BY message_id ASC
    """, (event_id, after))
    rows = cursor.fetchall()

    messages = []
    for message_id, student_id, admin_id, message, created_at in rows:
        author = get_admin_identity(admin_id) if admin_id else get_student_identity(student_id)
        messages.append({
            "message_id": message_id,
            "message": message,
            "created_at": created_at.strftime("%b %d, %I:%M %p") if created_at else "",
            "author": author,
            "can_delete": user.get("role") == "admin",
        })

    return jsonify({"ok": True, "messages": messages})


@app.route("/event/<int:event_id>/discussion/send", methods=["POST"])
def event_discussion_send(event_id):
    user = get_current_user()
    if not _can_access_discussion(event_id, user):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Message cannot be empty."})
    if len(text) > 2000:
        return jsonify({"ok": False, "error": "Message is too long."})

    if user.get("role") == "admin":
        cursor.execute(
            "INSERT INTO event_discussion_messages (event_id, admin_id, message) VALUES (%s, %s, %s)",
            (event_id, user["admin_id"], text)
        )
    else:
        cursor.execute(
            "INSERT INTO event_discussion_messages (event_id, student_id, message) VALUES (%s, %s, %s)",
            (event_id, user["user_id"], text)
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/event/<int:event_id>/discussion/delete/<int:message_id>", methods=["POST"])
def event_discussion_delete(event_id, message_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    cursor.execute(
        "DELETE FROM event_discussion_messages WHERE message_id=%s AND event_id=%s",
        (message_id, event_id)
    )
    db.commit()
    return jsonify({"ok": True})


# ─── COMMUNITY Q&A ──────────────────────────────────────────────────────────────
COMMUNITY_UNANSWERED_HOURS = 24

@app.route("/community")
def community():
    user = get_current_user()
    if not user or user.get("role") not in ("student", "admin"):
        return redirect("/student_login")

    tab = request.args.get("tab", "all")

    cursor.execute("""
        SELECT q.question_id, q.student_id, q.title, q.tags, q.status, q.created_at,
               (SELECT COUNT(*) FROM community_answers a WHERE a.question_id = q.question_id) AS answer_count
        FROM community_questions q
        ORDER BY q.created_at DESC
    """)
    rows = cursor.fetchall()

    now = datetime.datetime.now()
    questions = []
    for qid, student_id, title, tags, status, created_at, answer_count in rows:
        needs_attention = (
            answer_count == 0 and status == "open" and created_at is not None and
            (now - created_at).total_seconds() > COMMUNITY_UNANSWERED_HOURS * 3600
        )
        questions.append({
            "question_id": qid,
            "author": get_student_identity(student_id),
            "title": title,
            "tags": [t.strip() for t in tags.split(",")] if tags else [],
            "status": status,
            "created_at": created_at,
            "answer_count": answer_count,
            "needs_attention": needs_attention,
        })

    if tab == "unanswered":
        questions = [q for q in questions if q["answer_count"] == 0 and q["status"] == "open"]
    elif tab == "resolved":
        questions = [q for q in questions if q["status"] == "resolved"]

    return render_template("community.html", questions=questions, tab=tab, is_admin=(user.get("role") == "admin"))


@app.route("/community/ask", methods=["GET", "POST"])
def community_ask():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        tags = request.form.get("tags", "").strip()
        tags = ",".join(t.strip() for t in tags.split(",") if t.strip()) or None

        if not title or not body:
            flash("⚠ Please fill in both a title and a description of your doubt.")
            return render_template("community_ask.html", title=title, body=body, tags=tags or "")

        cursor.execute(
            "INSERT INTO community_questions (student_id, title, body, tags) VALUES (%s, %s, %s, %s)",
            (user["user_id"], title, body, tags)
        )
        db.commit()
        cursor.execute("SELECT LAST_INSERT_ID()")
        new_id = cursor.fetchone()[0]
        flash("✅ Your question has been posted to the community!")
        return redirect(f"/community/question/{new_id}")

    return render_template("community_ask.html", title="", body="", tags="")


@app.route("/community/question/<int:question_id>")
def community_question(question_id):
    user = get_current_user()
    if not user or user.get("role") not in ("student", "admin"):
        return redirect("/student_login")

    cursor.execute("""
        SELECT question_id, student_id, title, body, tags, status, accepted_answer_id, created_at
        FROM community_questions WHERE question_id=%s
    """, (question_id,))
    row = cursor.fetchone()
    if not row:
        abort(404)
    qid, asker_id, title, body, tags, status, accepted_answer_id, created_at = row
    question = {
        "question_id": qid,
        "author": get_student_identity(asker_id),
        "author_id": asker_id,
        "title": title,
        "body": body,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
        "status": status,
        "accepted_answer_id": accepted_answer_id,
        "created_at": created_at,
    }

    cursor.execute("""
        SELECT answer_id, student_id, body, flag_count, created_at
        FROM community_answers WHERE question_id=%s
        ORDER BY created_at ASC
    """, (question_id,))
    answers = []
    for answer_id, student_id, a_body, flag_count, a_created_at in cursor.fetchall():
        answers.append({
            "answer_id": answer_id,
            "author": get_student_identity(student_id),
            "author_id": student_id,
            "body": a_body,
            "flag_count": flag_count,
            "created_at": a_created_at,
            "is_accepted": answer_id == accepted_answer_id,
            "disputed": flag_count >= 2,
        })

    is_asker = user.get("role") == "student" and user["user_id"] == asker_id
    is_admin = user.get("role") == "admin"

    return render_template(
        "community_question.html",
        question=question, answers=answers,
        is_asker=is_asker, is_admin=is_admin,
        current_student_id=user.get("user_id"),
    )


@app.route("/community/question/<int:question_id>/answer", methods=["POST"])
def community_answer(question_id):
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    cursor.execute("SELECT question_id FROM community_questions WHERE question_id=%s", (question_id,))
    if not cursor.fetchone():
        abort(404)

    body = request.form.get("body", "").strip()
    if not body:
        flash("⚠ Answer cannot be empty.")
        return redirect(f"/community/question/{question_id}")

    cursor.execute(
        "INSERT INTO community_answers (question_id, student_id, body) VALUES (%s, %s, %s)",
        (question_id, user["user_id"], body)
    )
    db.commit()
    flash("✅ Your answer has been posted!")
    return redirect(f"/community/question/{question_id}")


@app.route("/community/answer/<int:answer_id>/accept", methods=["POST"])
def community_answer_accept(answer_id):
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    cursor.execute("""
        SELECT q.question_id, q.student_id
        FROM community_answers a
        JOIN community_questions q ON a.question_id = q.question_id
        WHERE a.answer_id=%s
    """, (answer_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Answer not found."}), 404
    question_id, asker_id = row
    if asker_id != user["user_id"]:
        return jsonify({"ok": False, "error": "Only the person who asked can accept an answer."}), 403

    cursor.execute(
        "UPDATE community_questions SET accepted_answer_id=%s, status='resolved' WHERE question_id=%s",
        (answer_id, question_id)
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/community/answer/<int:answer_id>/flag", methods=["POST"])
def community_answer_flag(answer_id):
    user = get_current_user()
    if not user or user.get("role") != "student":
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    cursor.execute("SELECT student_id FROM community_answers WHERE answer_id=%s", (answer_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Answer not found."}), 404
    if row[0] == user["user_id"]:
        return jsonify({"ok": False, "error": "You can't flag your own answer."})

    try:
        cursor.execute(
            "INSERT INTO community_answer_flags (answer_id, student_id) VALUES (%s, %s)",
            (answer_id, user["user_id"])
        )
        cursor.execute(
            "UPDATE community_answers SET flag_count = flag_count + 1 WHERE answer_id=%s",
            (answer_id,)
        )
        db.commit()
    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"ok": False, "error": "You already flagged this answer."})

    cursor.execute("SELECT flag_count FROM community_answers WHERE answer_id=%s", (answer_id,))
    return jsonify({"ok": True, "flag_count": cursor.fetchone()[0]})


@app.route("/community/question/<int:question_id>/delete", methods=["POST"])
def community_question_delete(question_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    cursor.execute("DELETE FROM community_answer_flags WHERE answer_id IN (SELECT answer_id FROM community_answers WHERE question_id=%s)", (question_id,))
    cursor.execute("DELETE FROM community_answers WHERE question_id=%s", (question_id,))
    cursor.execute("DELETE FROM community_questions WHERE question_id=%s", (question_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/community/answer/<int:answer_id>/delete", methods=["POST"])
def community_answer_delete(answer_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    cursor.execute("SELECT question_id FROM community_answers WHERE answer_id=%s", (answer_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute(
            "UPDATE community_questions SET accepted_answer_id=NULL WHERE question_id=%s AND accepted_answer_id=%s",
            (row[0], answer_id)
        )
    cursor.execute("DELETE FROM community_answer_flags WHERE answer_id=%s", (answer_id,))
    cursor.execute("DELETE FROM community_answers WHERE answer_id=%s", (answer_id,))
    db.commit()
    return jsonify({"ok": True})


# ─── DELETE EVENT ─────────────────────────────────────────────────────────────
@app.route("/delete_event/<int:event_id>")
def delete_event(event_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("DELETE FROM registrations WHERE event_id=%s", (event_id,))
    cursor.execute("DELETE FROM events WHERE event_id=%s", (event_id,))
    db.commit()
    return redirect("/admin_events")


# ─── EDIT EVENT ───────────────────────────────────────────────────────────────
@app.route("/edit_event/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    if request.method == "POST":
        event_name = request.form["event_name"]
        event_date = request.form["event_date"]
        venue      = request.form["venue"]
        max_seats  = request.form["max_seats"]

        cursor.execute("""
            UPDATE events SET event_name=%s, event_date=%s, venue=%s, max_seats=%s
            WHERE event_id=%s
        """, (event_name, event_date, venue, max_seats, event_id))
        db.commit()
        return redirect("/admin_events")

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    return render_template("edit_event.html", event=cursor.fetchone())


# ─── VIEW EVENT REGISTRATIONS (admin) ─────────────────────────────────────────
@app.route("/admin/event/<int:event_id>")
def view_event_registrations(event_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("""
        SELECT students.name, students.email, registrations.dept, registrations.registration_date
        FROM registrations
        JOIN students ON registrations.student_id = students.student_id
        WHERE registrations.event_id = %s
    """, (event_id,))

    return render_template("admin_event.html", students=cursor.fetchall())


# ─── VENUES ───────────────────────────────────────────────────────────────────
@app.route("/venues")
def venues():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("SELECT * FROM venues ORDER BY venue_name")
    all_venues = cursor.fetchall()
    return render_template("venues.html", venues=all_venues)


@app.route("/add_venue", methods=["POST"])
def add_venue():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    venue_name = request.form["venue_name"]
    location   = request.form["location"]
    capacity   = request.form["capacity"]

    cursor.execute(
        "INSERT INTO venues (venue_name, location, capacity) VALUES (%s, %s, %s)",
        (venue_name, location, capacity),
    )
    db.commit()
    flash("Venue added successfully 💖")
    return redirect("/venues")


@app.route("/edit_venue/<int:venue_id>", methods=["GET", "POST"])
def edit_venue(venue_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    if request.method == "POST":
        venue_name = request.form["venue_name"]
        location   = request.form["location"]
        capacity   = request.form["capacity"]
        cursor.execute(
            "UPDATE venues SET venue_name=%s, location=%s, capacity=%s WHERE venue_id=%s",
            (venue_name, location, capacity, venue_id),
        )
        db.commit()
        flash("Venue updated successfully 💖")
        return redirect("/venues")

    cursor.execute("SELECT * FROM venues WHERE venue_id=%s", (venue_id,))
    venue = cursor.fetchone()
    return render_template("edit_venue_form.html", venue=venue)


@app.route("/delete_venue/<int:venue_id>")
def delete_venue(venue_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("DELETE FROM venues WHERE venue_id=%s", (venue_id,))
    db.commit()
    flash("Venue deleted.")
    return redirect("/venues")


# ─── PERMISSIONS ──────────────────────────────────────────────────────────────
@app.route("/permissions", methods=["GET", "POST"])
def permissions():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    if request.method == "POST":
        admin_username         = request.form["admin_username"].strip()
        admin_email            = request.form.get("admin_email", "").strip()
        admin_password         = request.form.get("admin_password", "").strip()
        can_create_event       = "can_create_event"       in request.form
        can_delete_event       = "can_delete_event"       in request.form
        can_edit_event         = "can_edit_event"         in request.form
        can_view_registrations = "can_view_registrations" in request.form

        # Save / update permissions
        cursor.execute("""
            INSERT INTO permissions (admin_username, can_create_event, can_delete_event, can_edit_event, can_view_registrations)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                can_create_event=%s, can_delete_event=%s,
                can_edit_event=%s, can_view_registrations=%s
        """, (admin_username, can_create_event, can_delete_event, can_edit_event, can_view_registrations,
              can_create_event, can_delete_event, can_edit_event, can_view_registrations))
        db.commit()

        # Register admin account if email + password provided
        if admin_email and admin_password:
            cursor.execute("SELECT admin_id FROM admins WHERE username=%s OR email=%s", (admin_username, admin_email))
            existing = cursor.fetchone()
            if not existing:
                cursor.execute(
                    "INSERT INTO admins (username, email, password) VALUES (%s, %s, %s)",
                    (admin_username, admin_email, admin_password),
                )
                db.commit()
                try:
                    msg = Message("Your Admin Account — Event Bliss", recipients=[admin_email])
                    msg.body = (
                        f"Hi {admin_username},\n\n"
                        f"You have been registered as an admin on Event Bliss.\n\n"
                        f"Your login credentials:\n"
                        f"  Username : {admin_username}\n"
                        f"  Password : {admin_password}\n\n"
                        f"Login at: http://127.0.0.1:5000/admin_login\n\n"
                        f"Please change your password after first login.\n\n"
                        f"— Event Bliss Team"
                    )
                    mail.send(msg)
                    flash(f"Admin '{admin_username}' registered and permissions saved. Credentials sent to {admin_email}. 📧")
                except Exception as e:
                    app.logger.error(f"Admin credentials email error: {e}")
                    flash(f"Admin '{admin_username}' registered and permissions saved. (Email delivery failed.) ⚠")
            else:
                flash(f"Permissions for '{admin_username}' updated successfully. 💖")
        else:
            flash(f"Permissions for '{admin_username}' saved successfully. ✅")
        return redirect("/permissions")

    cursor.execute("SELECT * FROM permissions")
    all_perms = cursor.fetchall()
    return render_template("permissions.html", all_perms=all_perms)


@app.route("/delete_permission/<admin_username>")
def delete_permission(admin_username):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("DELETE FROM permissions WHERE admin_username=%s", (admin_username,))
    db.commit()
    flash(f"Permissions for '{admin_username}' deleted.")
    return redirect("/permissions")


# ─── GUEST RSVPs ──────────────────────────────────────────────────────────────
@app.route("/rsvp/<int:event_id>", methods=["GET", "POST"])
def rsvp(event_id):
    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date, events.event_time,
               COALESCE(venues.venue_name, events.venue) AS venue_display,
               events.organiser
        FROM events
        LEFT JOIN venues ON events.venue_id = venues.venue_id
        WHERE events.event_id=%s
    """, (event_id,))
    event = cursor.fetchone()
    if not event:
        abort(404)

    if request.method == "POST":
        name   = request.form["name"]
        email  = request.form["email"]
        phone  = request.form.get("phone", "")
        status = request.form.get("status", "attending")

        cursor.execute("""
            SELECT COUNT(*) FROM rsvps WHERE event_id = %s AND email = %s
        """, (event_id, email))
        already_submitted = cursor.fetchone()[0] > 0

        if already_submitted:
            flash("⚠️ This email has already submitted an RSVP for this event.")
            return redirect(f"/rsvp/{event_id}")

        cursor.execute("""
            INSERT INTO rsvps (event_id, name, email, phone, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (event_id, name, email, phone, status))
        db.commit()
        flash("RSVP submitted successfully 🎉")
        return redirect(f"/rsvp/{event_id}")

    return render_template("rsvp.html", event=event)


@app.route("/admin/event/<int:event_id>/rsvps")
def view_rsvps(event_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("SELECT event_name FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.execute("""
        SELECT name, email, phone, status, created_at
        FROM rsvps WHERE event_id=%s ORDER BY created_at DESC
    """, (event_id,))
    rsvps = cursor.fetchall()

    return render_template("admin_rsvps.html", event=event, rsvps=rsvps, event_id=event_id)


# ─── FORGOT / RESET PASSWORD ──────────────────────────────────────────────────
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        student = cursor.fetchone()
        if student:
            otp = str(random.randint(100000, 999999))
            session["student_reset_otp"] = {
                "student_id": student[0],
                "email":      email,
                "otp":        otp,
                "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat(),
            }
            msg = Message("Password Reset OTP — Event Bliss", recipients=[email])
            msg.body = (
                f"Hi {student[1]},\n\n"
                f"You requested a password reset for your Event Bliss account.\n\n"
                f"Your OTP is:\n\n"
                f"  {otp}\n\n"
                f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"— Event Bliss Team"
            )
            try:
                mail.send(msg)
            except Exception as e:
                app.logger.error(f"Student password reset OTP mail error: {e}")
                session.pop("student_reset_otp", None)
                flash("⚠ Could not send the reset email right now. Please try again in a few minutes.")
                return render_template("forgot_password.html")
            flash("A 6-digit OTP has been sent to your email 📧")
            return redirect("/verify_reset_otp")
        else:
            flash("No account found with that email ❌")
    return render_template("forgot_password.html")


@app.route("/verify_reset_otp", methods=["GET", "POST"])
def verify_reset_otp():
    pending = session.get("student_reset_otp")
    if not pending:
        flash("No pending password reset. Please try again.")
        return redirect("/forgot_password")

    if request.method == "POST":
        entered_otp = request.form["otp"].strip()
        expires_at  = datetime.datetime.fromisoformat(pending["expires_at"])

        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            session.pop("student_reset_otp", None)
            flash("OTP expired. Please request a new one. ⏰")
            return redirect("/forgot_password")

        if entered_otp != pending["otp"]:
            flash("Incorrect OTP. Please try again. ❌")
            return render_template("verify_reset_otp.html", email=pending["email"])

        session.pop("student_reset_otp", None)
        session["reset_student_id"] = pending["student_id"]
        return redirect("/reset_password_form")

    return render_template("verify_reset_otp.html", email=pending["email"])


@app.route("/reset_password_form", methods=["GET", "POST"])
def reset_password_form():
    student_id = session.get("reset_student_id")
    if not student_id:
        flash("Session expired. Please request a new OTP. ❌")
        return redirect("/forgot_password")

    if request.method == "POST":
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match ❌")
            return render_template("reset_password.html")

        pw_error = validate_password(password)
        if pw_error:
            flash(pw_error + " ❌")
            return render_template("reset_password.html")

        cursor.execute("UPDATE students SET password=%s WHERE student_id=%s", (password, student_id))
        db.commit()
        session.pop("reset_student_id", None)
        flash("Password updated successfully 💖")
        return redirect(url_for("student_login"))

    return render_template("reset_password.html")


# ─── ADMIN FORGOT PASSWORD ────────────────────────────────────────────────────
@app.route("/admin_forgot_password", methods=["GET", "POST"])
def admin_forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()
        cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin_user = cursor.fetchone()

        if admin_user:
            otp = str(random.randint(100000, 999999))
            session["admin_reset_otp"] = {
                "admin_id":   admin_user[0],
                "email":      email,
                "otp":        otp,
                "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat(),
            }
            msg = Message("Admin Password Reset OTP — Event Bliss", recipients=[email])
            msg.body = (
                f"Hi {admin_user[1]},\n\n"
                f"You requested a password reset for your admin account.\n\n"
                f"Your OTP is:\n\n"
                f"  {otp}\n\n"
                f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"— Event Bliss Team"
            )
            try:
                mail.send(msg)
            except Exception as e:
                app.logger.error(f"Admin password reset OTP mail error: {e}")
                session.pop("admin_reset_otp", None)
                flash("⚠ Could not send the reset email right now. Please try again in a few minutes.")
                return render_template("admin_forgot_password.html")
            flash("A 6-digit OTP has been sent to your email 📧")
            return redirect("/verify_admin_reset_otp")
        else:
            flash("No admin account found with that email ❌")

    return render_template("admin_forgot_password.html")


@app.route("/verify_admin_reset_otp", methods=["GET", "POST"])
def verify_admin_reset_otp():
    pending = session.get("admin_reset_otp")
    if not pending:
        flash("No pending admin password reset. Please try again.")
        return redirect("/admin_forgot_password")

    if request.method == "POST":
        entered_otp = request.form["otp"].strip()
        expires_at  = datetime.datetime.fromisoformat(pending["expires_at"])

        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            session.pop("admin_reset_otp", None)
            flash("OTP expired. Please request a new one. ⏰")
            return redirect("/admin_forgot_password")

        if entered_otp != pending["otp"]:
            flash("Incorrect OTP. Please try again. ❌")
            return render_template("verify_admin_reset_otp.html", email=pending["email"])

        session.pop("admin_reset_otp", None)
        session["reset_admin_id"] = pending["admin_id"]
        return redirect("/admin_reset_password_form")

    return render_template("verify_admin_reset_otp.html", email=pending["email"])


@app.route("/admin_reset_password_form", methods=["GET", "POST"])
def admin_reset_password_form():
    admin_id = session.get("reset_admin_id")
    if not admin_id:
        flash("Session expired. Please request a new OTP. ❌")
        return redirect("/admin_forgot_password")

    if request.method == "POST":
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match ❌")
            return render_template("admin_reset_password.html")

        pw_error = validate_password(password)
        if pw_error:
            flash(pw_error + " ❌")
            return render_template("admin_reset_password.html")

        cursor.execute("UPDATE admins SET password=%s WHERE admin_id=%s", (password, admin_id))
        db.commit()
        session.pop("reset_admin_id", None)
        flash("Admin password updated successfully 💖")
        return redirect("/admin_login")

    return render_template("admin_reset_password.html")


# ─── ERROR HANDLERS ───────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return render_template("errors/400.html"), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template("errors/401.html"), 401

@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404

@app.errorhandler(409)
def conflict(e):
    return render_template("errors/409.html"), 409

@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ─── EVENT REMINDER SCHEDULER ─────────────────────────────────────────────────
def _fmt_time(event_time):
    """Convert MySQL TIME (timedelta) to HH:MM string."""
    if isinstance(event_time, datetime.timedelta):
        total = int(event_time.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    return str(event_time) if event_time else "TBD"


def send_event_reminders():
    """Runs every hour. Emails students whose event starts within the next 24 hours."""
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "event_management"),
        )
        cur = conn.cursor()
        # ADDTIME(CAST(date AS DATETIME), time) is more reliable than TIMESTAMP(date, time)
        cur.execute("""
            SELECT r.reg_id, r.first_name, s.name,
                   COALESCE(r.notification_email, s.email) AS recipient_email,
                   e.event_name, e.event_date, e.event_time,
                   COALESCE(v.venue_name, e.venue) AS venue_display
            FROM registrations r
            JOIN events e ON r.event_id = e.event_id
            JOIN students s ON r.student_id = s.student_id
            LEFT JOIN venues v ON e.venue_id = v.venue_id
            WHERE r.reminder_sent = 0
              AND ADDTIME(CAST(e.event_date AS DATETIME), COALESCE(e.event_time, '00:00:00'))
                  BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 24 HOUR)
        """)
        rows = cur.fetchall()
        sent_count = 0
        with app.app_context():
            for reg_id, first_name, name, recipient_email, event_name, event_date, event_time, venue_display in rows:
                try:
                    display_name = first_name or name
                    msg = Message("Event Reminder — Event Bliss", recipients=[recipient_email])
                    msg.body = (
                        f"Hi {display_name},\n\n"
                        f"This is a reminder that you are registered for an upcoming event:\n\n"
                        f"  Event  : {event_name}\n"
                        f"  Date   : {event_date}\n"
                        f"  Time   : {_fmt_time(event_time)}\n"
                        f"  Venue  : {venue_display or 'TBD'}\n\n"
                        f"The event starts in less than 24 hours. See you there!\n\n"
                        f"— Event Bliss Team"
                    )
                    mail.send(msg)
                    cur.execute("UPDATE registrations SET reminder_sent = 1 WHERE reg_id = %s", (reg_id,))
                    conn.commit()
                    sent_count += 1
                except Exception as mail_err:
                    app.logger.error(f"Failed to send reminder to {recipient_email}: {mail_err}")

            # Send summary to admin after batch completes
            if sent_count > 0:
                try:
                    cur.execute("SELECT email FROM admins WHERE username='admin' LIMIT 1")
                    admin_row = cur.fetchone()
                    if admin_row:
                        summary = Message("Reminder Batch Summary — Event Bliss", recipients=[admin_row[0]])
                        summary.body = (
                            f"Hi Admin,\n\n"
                            f"The scheduled reminder job just completed.\n\n"
                            f"  Reminders sent : {sent_count}\n\n"
                            f"All students with events within the next 24 hours have been notified.\n\n"
                            f"— Event Bliss System"
                        )
                        mail.send(summary)
                except Exception as summary_err:
                    app.logger.error(f"Failed to send admin summary: {summary_err}")

        cur.close()
        conn.close()
    except Exception as e:
        app.logger.error(f"Reminder scheduler error: {e}")


# Start scheduler once. In Flask debug/reloader mode only run in the child process.
# WERKZEUG_RUN_MAIN is "true" in the child; unset in production (no reloader).
_werkzeug = os.environ.get("WERKZEUG_RUN_MAIN")
if _werkzeug == "true" or _werkzeug is None:
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        send_event_reminders, "interval", hours=1,
        next_run_time=datetime.datetime.now()   # run immediately on start
    )
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
