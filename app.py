from flask import Flask, render_template, request, redirect, session , flash
from flask_mail import Mail, Message
from flask import abort
import mysql.connector

app = Flask(__name__)
app.secret_key = "my_super_secret_key_123"




# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Rushitha@07",
    database="event_management"
)

cursor = db.cursor()


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- REGISTER ----------------


"""@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        name = request.form["name"]
        cursor.execute(
            "INSERT INTO students (name , email, password) VALUES (%s, %s, %s)",
            (name, email, password)
        )
        db.commit()

        return redirect("/login?role=student")

    return render_template("register.html")"""


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # 🔍 Check if email already exists
        cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return render_template("register.html", error="Account already exists. Please login 💌")

        # If not exists → insert
        cursor.execute(
            "INSERT INTO students (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password)
        )
        db.commit()

        return redirect("/login?role=student")

    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.args.get("role")

    if request.method == "POST":
        role = request.form.get("role")

        if role == "student":
            email = request.form["email"]
            password = request.form["password"]

            sql = "SELECT * FROM students WHERE email=%s AND password=%s"
            cursor.execute(sql, (email, password))
            user = cursor.fetchone()

            if user:
                session["user_id"] = user[0]
                session["user_name"] = user[1]
                return redirect("/dashboard")
            else:
                flash("Invalid Student Credentials ❌ .")
                return redirect("/login?role=student")

        elif role == "admin":
            username = request.form["username"]
            password = request.form["password"]

            if username == "admin" and password == "admin123":
                session["admin"] = True
                return redirect("/admin_dashboard")
            else:
                flash("Invalid Admin Credentials ❌")
                return redirect("/login?role=admin")

    return render_template("login.html", role=role)

"""@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form["role"]

        if role == "student":
            email = request.form["email"]
            password = request.form["password"]

            sql = "SELECT * FROM students WHERE email=%s AND password=%s"
            cursor.execute(sql, (email, password))
            user = cursor.fetchone()

            if user:
                session["user_id"] = user[0]
                session["user_name"] = user[1]
                return redirect("/dashboard")
            else:
                return "Invalid Student Credentials"

        elif role == "admin":
            username = request.form["username"]
            password = request.form["password"]

            if username == "admin" and password == "admin123":
                session["admin"] = True
                return redirect("/admin_dashboard")
            else:
                return "Invalid Admin Credentials"

    return render_template("login.html")"""


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("dashboard.html", name=session["user_name"])


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            session["admin"] = True
            return redirect("/admin_dashboard")
        else:
            flash("Invalid Admin Credentials ❌")
            return redirect(f"/login?role=admin")

    return render_template("admin.html")

@app.route("/select_role")
def select_role():
    return render_template("select_role.html")

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        sql = "SELECT * FROM students WHERE email=%s AND password=%s"
        cursor.execute(sql, (email, password))
        user = cursor.fetchone()

        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect("/dashboard")
        else:
            flash("Invalid Student Credentials ❌")
            return redirect(f"/login?role=student")

    return render_template("student_login.html")



@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/login")

    # Total Events
    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    # Total Students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Total Registrations
    cursor.execute("SELECT COUNT(*) FROM registrations")
    total_registrations = cursor.fetchone()[0]

    return render_template(
        "admin_dashboard.html",
        total_events=total_events,
        total_students=total_students,
        total_registrations=total_registrations
    )


@app.route("/admin_events")
def admin_events():
    if "admin" not in session:
        return redirect("/select_role")

    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    return render_template("admin_events.html", events=events)

# ---------------- CREATE EVENT ----------------
@app.route("/create_event", methods=["GET", "POST"])
def create_event():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        event_name = request.form["event_name"]
        event_date = request.form["event_date"]
        venue = request.form["venue"]
        max_seats = request.form["max_seats"]
        event_time = request.form["event_time"]
        theme = request.form["theme"]
        requirements = request.form["requirements"]


        sql = """
        INSERT INTO events
        (event_name, event_date, event_time, venue, max_seats, theme, requirements)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (event_name, event_date, event_time, venue, max_seats, theme, requirements)


        cursor.execute(sql, values)
        db.commit()

        return "Event Created Successfully!"

    return render_template("create_event.html")


@app.route("/events")
def events():
    if "user_id" not in session:
        return redirect("/student_login")

    student_id = session["user_id"]

    # Get all events with seats remaining
    sql = """
    SELECT e.event_id, e.event_name, e.event_date, e.venue,
           e.max_seats - COUNT(r.event_id) AS seats_remaining
    FROM events e
    LEFT JOIN registrations r ON e.event_id = r.event_id
    GROUP BY e.event_id
    """

    cursor.execute(sql)
    all_events = cursor.fetchall()

    # 🔥 Get events already registered by this student
    cursor.execute("""
        SELECT event_id FROM registrations
        WHERE student_id = %s
    """, (student_id,))

    registered = cursor.fetchall()

    # Convert to simple list
    registered_event_ids = [r[0] for r in registered]

    return render_template(
        "events.html",
        events=all_events,
        registered_event_ids=registered_event_ids
    )



@app.route("/delete_event/<int:event_id>")
def delete_event(event_id):
    if "admin" not in session:
        return redirect("/admin_login")

    cursor.execute("DELETE FROM registrations WHERE event_id=%s", (event_id,))
    cursor.execute("DELETE FROM events WHERE event_id=%s", (event_id,))
    db.commit()

    return redirect("/admin/events")


@app.route("/edit_event/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    if "admin" not in session:
        return redirect("/admin_login")

    if request.method == "POST":
        event_name = request.form["event_name"]
        event_date = request.form["event_date"]
        venue = request.form["venue"]
        max_seats = request.form["max_seats"]

        sql = """
        UPDATE events
        SET event_name=%s, event_date=%s, venue=%s, max_seats=%s
        WHERE event_id=%s
        """
        cursor.execute(sql, (event_name, event_date, venue, max_seats, event_id))
        db.commit()

        return redirect("/admin/events")

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    return render_template("edit_event.html", event=event)


@app.route("/register_event/<int:event_id>", methods=["GET", "POST"])
def register_event(event_id):
    if "user_id" not in session:
        return redirect("/student_login")

    student_id = session["user_id"]

    # 🔹 Check if already registered FIRST
    cursor.execute("""
        SELECT * FROM registrations
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    existing = cursor.fetchone()

    if existing:
        """return "You have already registered for this event!"""
        abort(409)

    # 🔹 Get event details
    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    if request.method == "POST":

        first_name = request.form["first_name"]
        middle_name = request.form["middle_name"]
        last_name = request.form["last_name"]
        year = request.form["year"]
        dept = request.form["dept"]
        section = request.form["section"]
        roll_no = request.form["roll_no"]
        phone = request.form["phone"]

        sql = """
        INSERT INTO registrations
        (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (student_id, event_id, first_name, middle_name, last_name,
                  year, dept, section, roll_no, phone)

        cursor.execute(sql, values)
        db.commit()

        flash("Registration Successful 💖")
        return redirect("/my_events")

    return render_template("event_registration_form.html", event=event)



@app.route("/my_events")
def my_events():
    if "user_id" not in session:
        return redirect("/login")

    student_id = session["user_id"]

    sql = """
    SELECT events.event_name, events.event_date, events.venue
    FROM registrations
    JOIN events ON registrations.event_id = events.event_id
    WHERE registrations.student_id = %s
    """

    cursor.execute(sql, (student_id,))
    registered_events = cursor.fetchall()

    return render_template("my_events.html", events=registered_events)


@app.route("/admin/event/<int:event_id>")
def view_event_registrations(event_id):
    if "admin" not in session:
        return redirect("/admin")

    cursor.execute("""
        SELECT students.name, students.email, registrations.registration_date
        FROM registrations
        JOIN students ON registrations.student_id = students.student_id
        WHERE registrations.event_id = %s
    """, (event_id,))

    students = cursor.fetchall()

    return render_template("admin_event.html", students=students)


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


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
