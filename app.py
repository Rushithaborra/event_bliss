from flask import Flask, render_template, request, redirect, session, flash, make_response, abort, url_for
from flask_mail import Mail, Message
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import mysql.connector
import jwt
import datetime
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret")

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
            (name, email, "GOOGLE_OAUTH"),   # no password needed for OAuth users
        )
        db.commit()
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        user = cursor.fetchone()

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

        if username == "admin" and password == "admin123":
            response = make_response(redirect("/admin_dashboard"))
            set_jwt_cookie(response, {"role": "admin"})
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
        SELECT students.name, students.email, registrations.registration_date
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
        admin_username        = request.form["admin_username"]
        can_create_event      = "can_create_event"      in request.form
        can_delete_event      = "can_delete_event"      in request.form
        can_edit_event        = "can_edit_event"        in request.form
        can_view_registrations = "can_view_registrations" in request.form

        cursor.execute("""
            INSERT INTO permissions (admin_username, can_create_event, can_delete_event, can_edit_event, can_view_registrations)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                can_create_event=%s, can_delete_event=%s,
                can_edit_event=%s, can_view_registrations=%s
        """, (admin_username, can_create_event, can_delete_event, can_edit_event, can_view_registrations,
              can_create_event, can_delete_event, can_edit_event, can_view_registrations))
        db.commit()
        flash("Permissions updated 💖")
        return redirect("/permissions")

    cursor.execute("SELECT * FROM permissions")
    all_perms = cursor.fetchall()
    return render_template("permissions.html", all_perms=all_perms)


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
        email = request.form["email"]
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        if cursor.fetchone():
            session["reset_email"] = email
            return redirect("/reset_password")
        else:
            flash("Email not found")
    return render_template("forgot_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if "reset_email" not in session:
        return redirect("/student_login")

    if request.method == "POST":
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]
        email            = session["reset_email"]

        if password != confirm_password:
            flash("Passwords do not match ❌")
            return render_template("reset_password.html")

        cursor.execute("UPDATE students SET password=%s WHERE email=%s", (password, email))
        db.commit()
        session.pop("reset_email", None)
        flash("Password updated successfully 💖")
        return redirect(url_for("student_login"))

    return render_template("reset_password.html")


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
