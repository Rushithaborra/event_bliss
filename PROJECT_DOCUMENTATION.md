# EventBliss — Event Management System
### Database Project Documentation

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Database Design](#3-database-design)
4. [Entity-Relationship Diagram](#4-entity-relationship-diagram)
5. [SQL Queries Used](#5-sql-queries-used)
6. [Application Features](#6-application-features)
7. [Authentication & Security](#7-authentication--security)
8. [User Flows](#8-user-flows)
9. [Project Structure](#9-project-structure)
10. [Feature Improvements](#10-feature-improvements)

---

## 1. Project Overview

**EventBliss** is a full-stack web-based Event Management System built for a college environment. It allows students to browse and register for events, and provides admins with tools to manage events, venues, registrations, and sub-admin permissions — all backed by a relational MySQL database.

**Key Goals:**
- Demonstrate real-world database design with multiple related tables
- Implement secure authentication using JWT tokens and Google OAuth
- Show practical use of SQL operations: INSERT, UPDATE, DELETE, JOIN, COUNT, ON DUPLICATE KEY UPDATE
- Apply role-based access control at the database and application level

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9, Flask |
| Database | MySQL (via mysql-connector-python) |
| Authentication | JWT (PyJWT), Google OAuth 2.0 (Authlib) |
| Email | Flask-Mail (Gmail SMTP, TLS) |
| Frontend | HTML, CSS (custom glass-card UI), Jinja2 templates |
| Environment | python-dotenv (.env config) |

---

## 3. Database Design

### Tables

#### `students`
Stores all registered student accounts.

| Column | Type | Constraints |
|--------|------|-------------|
| student_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(100) | NOT NULL |
| email | VARCHAR(200) | UNIQUE, NOT NULL |
| password | VARCHAR(255) | NOT NULL (`GOOGLE_OAUTH` for OAuth users) |

---

#### `admins`
Stores admin accounts (created via permissions page).

| Column | Type | Constraints |
|--------|------|-------------|
| admin_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| username | VARCHAR(100) | UNIQUE, NOT NULL |
| email | VARCHAR(200) | UNIQUE, NOT NULL |
| password | VARCHAR(255) | NOT NULL |

---

#### `events`
Stores all events created by admins.

| Column | Type | Constraints |
|--------|------|-------------|
| event_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| event_name | VARCHAR(200) | NOT NULL |
| event_date | DATE | |
| event_time | TIME | |
| venue | VARCHAR(200) | (legacy text field) |
| venue_id | INT | FOREIGN KEY → venues(venue_id) |
| max_seats | INT | |
| theme | VARCHAR(200) | |
| requirements | TEXT | |
| organiser | VARCHAR(200) | |

---

#### `venues`
Stores venue information linked to events.

| Column | Type | Constraints |
|--------|------|-------------|
| venue_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| venue_name | VARCHAR(200) | NOT NULL |
| location | VARCHAR(200) | |
| capacity | INT | |

---

#### `registrations`
Junction table linking students to events (many-to-many).

| Column | Type | Constraints |
|--------|------|-------------|
| registration_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| student_id | INT | FOREIGN KEY → students(student_id) |
| event_id | INT | FOREIGN KEY → events(event_id) |
| first_name | VARCHAR(100) | |
| middle_name | VARCHAR(100) | |
| last_name | VARCHAR(100) | |
| year | VARCHAR(10) | |
| dept | VARCHAR(100) | |
| section | VARCHAR(10) | |
| roll_no | VARCHAR(50) | |
| phone | VARCHAR(20) | |
| registration_date | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

#### `permissions`
Stores fine-grained permissions for each admin username.

| Column | Type | Constraints |
|--------|------|-------------|
| permission_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| admin_username | VARCHAR(100) | UNIQUE (used for ON DUPLICATE KEY UPDATE) |
| can_create_event | BOOLEAN | |
| can_delete_event | BOOLEAN | |
| can_edit_event | BOOLEAN | |
| can_view_registrations | BOOLEAN | |

---

#### `rsvps`
Stores RSVPs from guests (non-student attendees).

| Column | Type | Constraints |
|--------|------|-------------|
| rsvp_id | INT | PRIMARY KEY, AUTO_INCREMENT |
| event_id | INT | FOREIGN KEY → events(event_id) |
| name | VARCHAR(200) | NOT NULL |
| email | VARCHAR(200) | NOT NULL |
| phone | VARCHAR(20) | |
| status | ENUM('attending','not attending','maybe') | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

## 4. Entity-Relationship Diagram

```
┌─────────────┐         ┌───────────────────┐         ┌──────────────┐
│   students  │         │   registrations   │         │    events    │
│─────────────│         │───────────────────│         │──────────────│
│ student_id  │◄───────►│ student_id  (FK)  │◄───────►│ event_id     │
│ name        │  1   N  │ event_id    (FK)  │  N   1  │ event_name   │
│ email       │         │ dept              │         │ event_date   │
│ password    │         │ roll_no           │         │ venue_id(FK) │
└─────────────┘         │ phone             │         │ max_seats    │
                        │ year              │         │ organiser    │
                        └───────────────────┘         └──────┬───────┘
                                                             │
                                                           N │
                                                             ▼ 1
┌─────────────┐         ┌───────────────────┐         ┌──────────────┐
│   admins    │         │   permissions     │         │    venues    │
│─────────────│         │───────────────────│         │──────────────│
│ admin_id    │         │ admin_username    │         │ venue_id     │
│ username    │────────►│ can_create_event  │         │ venue_name   │
│ email       │  1   1  │ can_delete_event  │         │ location     │
│ password    │         │ can_edit_event    │         │ capacity     │
└─────────────┘         │ can_view_reg...   │         └──────────────┘
                        └───────────────────┘

                        ┌───────────────────┐
                        │      rsvps        │
                        │───────────────────│
                        │ rsvp_id           │
                        │ event_id    (FK)  │◄──── events
                        │ name              │
                        │ email             │
                        │ status            │
                        └───────────────────┘
```

**Relationships:**
- `students` ↔ `events` : Many-to-Many (through `registrations`)
- `events` → `venues` : Many-to-One (each event has one venue)
- `admins` → `permissions` : One-to-One (each admin has one permissions row)
- `events` → `rsvps` : One-to-Many (an event can have many RSVPs)

---

## 5. SQL Queries Used

### INSERT
```sql
-- Register a student
INSERT INTO students (name, email, password) VALUES (%s, %s, %s);

-- Register for an event
INSERT INTO registrations
  (student_id, event_id, first_name, middle_name, last_name, year, dept, section, roll_no, phone)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);

-- Add a venue
INSERT INTO venues (venue_name, location, capacity) VALUES (%s, %s, %s);
```

### SELECT with JOIN
```sql
-- Get all events with their venue name
SELECT events.event_id, events.event_name, events.event_date,
       COALESCE(venues.venue_name, events.venue) AS venue_display,
       events.max_seats, events.organiser
FROM events
LEFT JOIN venues ON events.venue_id = venues.venue_id;

-- Get registered students for an event (with department)
SELECT students.name, students.email, registrations.dept, registrations.registration_date
FROM registrations
JOIN students ON registrations.student_id = students.student_id
WHERE registrations.event_id = %s;

-- Get events a student is registered for
SELECT events.event_name, events.event_date, events.venue
FROM registrations
JOIN events ON registrations.event_id = events.event_id
WHERE registrations.student_id = %s;
```

### SELECT with COUNT (Dashboard stats)
```sql
SELECT COUNT(*) FROM events;
SELECT COUNT(*) FROM students;
SELECT COUNT(*) FROM registrations;
SELECT COUNT(*) FROM venues;
SELECT COUNT(*) FROM rsvps;
```

### UPDATE
```sql
-- Reset student password
UPDATE students SET password=%s WHERE student_id=%s;

-- Reset admin password
UPDATE admins SET password=%s WHERE admin_id=%s;

-- Edit event
UPDATE events SET event_name=%s, event_date=%s, venue=%s, max_seats=%s
WHERE event_id=%s;

-- Edit venue
UPDATE venues SET venue_name=%s, location=%s, capacity=%s WHERE venue_id=%s;
```

### INSERT ... ON DUPLICATE KEY UPDATE (Upsert)
```sql
-- Set or update admin permissions
INSERT INTO permissions
  (admin_username, can_create_event, can_delete_event, can_edit_event, can_view_registrations)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  can_create_event=%s, can_delete_event=%s,
  can_edit_event=%s, can_view_registrations=%s;
```

### DELETE
```sql
-- Delete event and its registrations (referential cleanup)
DELETE FROM registrations WHERE event_id=%s;
DELETE FROM events WHERE event_id=%s;

-- Delete a venue
DELETE FROM venues WHERE venue_id=%s;

-- Delete admin permissions
DELETE FROM permissions WHERE admin_username=%s;
```

### CREATE TABLE (Auto-run on startup)
```sql
CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email    VARCHAR(200) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);
```

---

## 6. Application Features

### Student Side
| Feature | Description |
|---------|-------------|
| Register | Create account with name, email, password |
| Login | Email + password or Google OAuth |
| Google OAuth | Sign in with Google — triggers email verification |
| Forgot Password | Email-based JWT reset link |
| Browse Events | View all events with seat availability |
| Register for Event | Fill detailed form (name, dept, roll no, phone, year, section) |
| My Events | View personal registered events |

### Admin Side
| Feature | Description |
|---------|-------------|
| Admin Login | DB-backed credentials (not hardcoded) |
| Forgot Password | JWT reset link sent to admin email |
| Dashboard | Live counts: events, students, registrations, venues, RSVPs |
| Create Event | Full event form with venue selector |
| Edit Event | Update event details |
| Delete Event | Removes event and all its registrations |
| View Registrations | See all students registered for an event (with department) |
| Manage Venues | Add, Edit, Delete venues |
| Guest RSVPs | View RSVPs from non-student attendees |
| Permissions | Register new sub-admins, send credentials by email, set/edit/delete permissions |

---

## 7. Authentication & Security

### JWT (JSON Web Tokens)
All sessions are managed via signed JWT cookies instead of server-side sessions.

```
Token payload example:
{
  "user_id": 42,
  "user_name": "Rushitha",
  "role": "student",
  "exp": <24 hours from now>
}
```

- Stored as an `HttpOnly` cookie (not accessible via JavaScript)
- Signed with `JWT_SECRET` using HS256 algorithm
- Every protected route calls `get_current_user()` to verify the token

### Secure Flows
| Flow | Mechanism |
|------|-----------|
| Student forgot password | JWT token (purpose: `student_reset`) sent via email |
| Admin forgot password | JWT token (purpose: `admin_reset`) sent via email |
| Google OAuth verification | JWT token (purpose: `google_verify`) sent via email |
| All reset links | Expire in 24 hours; `purpose` field prevents token reuse across flows |

### Role-Based Access Control
- Every admin route checks `user.get("role") != "admin"` before serving
- Admin permissions (create/edit/delete/view) are stored in DB and checked per action
- `abort(403)` is returned when a permission is denied

---

## 8. User Flows

### Student Registration & Login
```
Register → student_login → dashboard
                ↓
         Forgot Password → Enter Email → JWT link sent to email
                → Click link → Reset Password → student_login
```

### Google OAuth with Email Verification
```
Click "Continue with Google" → Google Account Selection
→ google_callback → Email sent with verification link
→ Click link in email → /verify_google_login/<token> → dashboard
```

### Admin Sub-Admin Creation
```
Admin → Permissions Page → Fill username + email + password + permissions
→ New admin created in DB → Credentials emailed to new admin
→ New admin logs in at /admin_login
→ Their permissions control what they can do
```

---

## 9. Project Structure

```
event_management_project/
│
├── app.py                  # All routes and business logic
├── .env                    # Secrets (DB, JWT, Google OAuth, Mail)
│
├── templates/
│   ├── home.html
│   ├── select_role.html
│   ├── register.html
│   ├── student_login.html
│   ├── dashboard.html
│   ├── events.html
│   ├── event_registration_form.html
│   ├── my_events.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   │
│   ├── admin.html                  # Admin login
│   ├── admin_dashboard.html
│   ├── admin_events.html
│   ├── admin_event.html            # View registrations for an event
│   ├── create_event.html
│   ├── edit_event.html
│   ├── venues.html
│   ├── edit_venue_form.html
│   ├── permissions.html
│   ├── admin_forgot_password.html
│   ├── admin_reset_password.html
│   ├── rsvp.html
│   ├── admin_rsvps.html
│   │
│   └── errors/
│       ├── 400.html
│       ├── 401.html
│       ├── 403.html
│       ├── 404.html
│       ├── 409.html
│       └── 500.html
│
└── static/
    └── style.css
```

---

## 10. Feature Improvements

The following enhancements would make EventBliss production-ready:

### Database & Security
| Improvement | Why |
|-------------|-----|
| **Password hashing** (bcrypt/argon2) | Passwords are currently stored in plaintext — hashing is essential for real deployments |
| **Foreign key constraints** | Add `ON DELETE CASCADE` to clean up child records automatically |
| **Database indexing** | Add indexes on `email`, `event_id`, `student_id` for faster queries on large datasets |
| **Connection pooling** | Replace the single `cursor` with a connection pool to handle concurrent users safely |
| **Prepared statements / ORM** | Use SQLAlchemy to prevent potential SQL injection and simplify queries |

### Features
| Improvement | Why |
|-------------|-----|
| **Email OTP instead of link** | A 6-digit OTP is more user-friendly for mobile users than clicking email links |
| **Event categories & filters** | Students can filter events by dept, date, or theme |
| **Waitlist system** | When max_seats is reached, students join a waitlist and get notified if a seat opens |
| **Attendance tracking** | Admin marks attendance on event day; stored in a new `attendance` table |
| **Certificate generation** | Auto-generate PDF certificates for students who attended events |
| **Student profile page** | Students can view and edit their own profile details |
| **Event search** | Full-text search across event name, organiser, theme |
| **Notifications** | Email reminders 24 hours before a registered event |
| **Analytics dashboard** | Charts showing registration trends, popular events, dept-wise breakdown |
| **Mobile-responsive UI** | Make the CSS fully responsive for phone screens |

### Architecture
| Improvement | Why |
|-------------|-----|
| **Blueprints** | Split routes into Flask Blueprints (student, admin, auth) for better organisation |
| **Environment separation** | Separate dev / staging / production configs |
| **Logging** | Log all login attempts and admin actions for an audit trail |
| **Rate limiting** | Prevent brute-force login attacks using Flask-Limiter |

---

*Project by Rushitha Borra | EventBliss — Event Management System*
