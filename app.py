from flask import Flask, render_template, request, redirect, session, flash, make_response, abort, url_for
from flask_mail import Mail, Message
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import mysql.connector
import jwt
import datetime
import os

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

# ─── MAIL CONFIG ───────────────────────────────────────────────────────────────
app.config["MAIL_SERVER"]   = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"]     = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")
mail = Mail(app)

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
db = mysql.connector.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_NAME", "event_management")
)
cursor = db.cursor()

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
    return render_template("home.html")


# ─── REGISTER ─────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form["name"]
        email    = request.form["email"]
        password = request.form["password"]

        if not name or not email or not password:
            abort(400)

        cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
        if cursor.fetchone():
            return render_template("register.html", error="Account already exists. Please login 💌")

        cursor.execute(
            "INSERT INTO students (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password),
        )
        db.commit()
        return redirect("/student_login")

    return render_template("register.html")


# ─── SELECT ROLE ──────────────────────────────────────────────────────────────
@app.route("/select_role")
def select_role():
    return render_template("select_role.html")


# ─── STUDENT LOGIN (email/password) ───────────────────────────────────────────
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM students WHERE email=%s AND password=%s", (email, password))
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
            flash("Invalid email or password ❌")

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

    # Send email verification before granting access
    verify_token = create_jwt({
        "purpose":   "google_verify",
        "user_id":   user[0],
        "user_name": user[1],
        "email":     email,
    })
    verify_link = url_for("verify_google_login", token=verify_token, _external=True)
    msg = Message("Verify Your Login — Event Bliss", recipients=[email])
    msg.body = (
        f"Hi {name},\n\n"
        f"You just signed in with Google to Event Bliss.\n\n"
        f"Click the link below to complete your login (valid for {JWT_EXPIRY_HOURS} hour(s)):\n"
        f"{verify_link}\n\n"
        f"If you did not attempt to log in, ignore this email.\n\n"
        f"— Event Bliss Team"
    )
    mail.send(msg)
    flash(f"A verification link has been sent to {email}. Please check your inbox. 📧")
    return redirect("/student_login")


@app.route("/verify_google_login/<token>")
def verify_google_login(token):
    payload = verify_jwt(token)
    if not payload or payload.get("purpose") != "google_verify":
        flash("Invalid or expired verification link ❌")
        return redirect("/student_login")

    response = make_response(redirect("/dashboard"))
    set_jwt_cookie(response, {
        "user_id":   payload["user_id"],
        "user_name": payload["user_name"],
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
            flash("Invalid Admin Credentials ❌")

    return render_template("admin.html")


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


# ─── ADMIN EVENTS ─────────────────────────────────────────────────────────────
@app.route("/admin_events")
def admin_events():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return redirect("/admin_login")

    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date,
               COALESCE(venues.venue_name, events.venue) AS venue_display,
               events.max_seats, events.organiser
        FROM events
        LEFT JOIN venues ON events.venue_id = venues.venue_id
    """)
    events = cursor.fetchall()
    perms = get_admin_permissions()
    return render_template("admin_events.html", events=events, perms=perms)


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


# ─── EVENTS (student view) ────────────────────────────────────────────────────
@app.route("/events")
def events():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    user_id = user["user_id"]

    cursor.execute("""
        SELECT events.event_id, events.event_name, events.event_date,
               events.venue, events.max_seats,
               COUNT(registrations.event_id) AS registered
        FROM events
        LEFT JOIN registrations ON events.event_id = registrations.event_id
        GROUP BY events.event_id
    """)
    all_events = cursor.fetchall()

    cursor.execute("SELECT event_id FROM registrations WHERE student_id=%s", (user_id,))
    registered_events = [r[0] for r in cursor.fetchall()]

    return render_template("events.html", events=all_events, registered_events=registered_events)


# ─── REGISTER FOR EVENT ───────────────────────────────────────────────────────
@app.route("/register_event/<int:event_id>", methods=["GET", "POST"])
def register_event(event_id):
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    student_id = user["user_id"]

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    if request.method == "POST":
        first_name  = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        last_name   = request.form.get("last_name")
        year        = request.form.get("year")
        dept        = request.form.get("dept")
        section     = request.form.get("section")
        roll_no     = request.form.get("roll_no")
        phone       = request.form.get("phone")

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
            )

        cursor.execute(
            "SELECT * FROM registrations WHERE student_id=%s AND event_id=%s",
            (student_id, event_id),
        )
        if cursor.fetchone():
            abort(409)

        cursor.execute("""
            INSERT INTO registrations
            (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone))
        db.commit()

        flash("Registration Successful 💖")
        return redirect("/my_events")

    return render_template("event_registration_form.html", event=event)


# ─── MY EVENTS ────────────────────────────────────────────────────────────────
@app.route("/my_events")
def my_events():
    user = get_current_user()
    if not user or user.get("role") != "student":
        return redirect("/student_login")

    cursor.execute("""
        SELECT events.event_name, events.event_date, events.venue
        FROM registrations
        JOIN events ON registrations.event_id = events.event_id
        WHERE registrations.student_id = %s
    """, (user["user_id"],))

    return render_template("my_events.html", events=cursor.fetchall())


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

        # Register admin account if email + password provided and not already in admins table
        if admin_email and admin_password:
            cursor.execute("SELECT admin_id FROM admins WHERE username=%s OR email=%s", (admin_username, admin_email))
            existing = cursor.fetchone()
            if not existing:
                cursor.execute(
                    "INSERT INTO admins (username, email, password) VALUES (%s, %s, %s)",
                    (admin_username, admin_email, admin_password),
                )
                db.commit()
                # Send credentials via email
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
                flash(f"Admin '{admin_username}' registered and credentials sent to {admin_email} 📧")
            else:
                flash(f"Admin '{admin_username}' already exists — permissions updated.")

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
        if not admin_email:
            flash("Permissions updated 💖")
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
            token = create_jwt({"purpose": "student_reset", "student_id": student[0], "email": email})
            reset_link = url_for("reset_password", token=token, _external=True)
            msg = Message("Password Reset — Event Bliss", recipients=[email])
            msg.body = (
                f"Hi {student[1]},\n\n"
                f"You requested a password reset for your Event Bliss account.\n\n"
                f"Click the link below to reset your password (valid for {JWT_EXPIRY_HOURS} hour(s)):\n"
                f"{reset_link}\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"— Event Bliss Team"
            )
            mail.send(msg)
            flash("Password reset link sent to your email 📧")
            return redirect("/forgot_password")
        else:
            flash("No account found with that email ❌")
    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    payload = verify_jwt(token)
    if not payload or payload.get("purpose") != "student_reset":
        flash("Invalid or expired reset link ❌")
        return redirect("/forgot_password")

    student_id = payload["student_id"]

    if request.method == "POST":
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match ❌")
            return render_template("reset_password.html", token=token)

        cursor.execute("UPDATE students SET password=%s WHERE student_id=%s", (password, student_id))
        db.commit()
        flash("Password updated successfully 💖")
        return redirect(url_for("student_login"))

    return render_template("reset_password.html", token=token)


# ─── ADMIN FORGOT PASSWORD ────────────────────────────────────────────────────
@app.route("/admin_forgot_password", methods=["GET", "POST"])
def admin_forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()
        cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin_user = cursor.fetchone()

        if admin_user:
            token = create_jwt({"purpose": "admin_reset", "admin_id": admin_user[0], "email": email})
            reset_link = url_for("admin_reset_password", token=token, _external=True)
            msg = Message("Admin Password Reset — Event Bliss", recipients=[email])
            msg.body = (
                f"Hi {admin_user[1]},\n\n"
                f"You requested a password reset for your admin account.\n\n"
                f"Click the link below to reset your password (valid for {JWT_EXPIRY_HOURS} hour(s)):\n"
                f"{reset_link}\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"— Event Bliss Team"
            )
            mail.send(msg)
            flash("Password reset link sent to your email 📧")
            return redirect("/admin_forgot_password")
        else:
            flash("No admin account found with that email ❌")

    return render_template("admin_forgot_password.html")


@app.route("/admin_reset_password/<token>", methods=["GET", "POST"])
def admin_reset_password(token):
    payload = verify_jwt(token)
    if not payload or payload.get("purpose") != "admin_reset":
        flash("Invalid or expired reset link ❌")
        return redirect("/admin_forgot_password")

    admin_id = payload["admin_id"]

    if request.method == "POST":
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match ❌")
            return render_template("admin_reset_password.html", token=token)

        cursor.execute("UPDATE admins SET password=%s WHERE admin_id=%s", (password, admin_id))
        db.commit()
        flash("Admin password updated successfully 💖")
        return redirect("/admin_login")

    return render_template("admin_reset_password.html", token=token)


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


# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
