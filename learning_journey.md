# DBMS Major Project – Learning Journey

## Day 1 – Project Setup & Environment Configuration

Today I started building my DBMS major project: 
College Event Management System using Python (Flask) and MySQL.

### What I Learned:
- How to create a structured backend project folder
- Why virtual environments are important
- How to install Flask using pip
- How to isolate dependencies using venv

### Key Concepts Understood:
- 3-tier architecture (Frontend, Backend, Database)
- Role of Flask as backend framework
- Importance of project structure in web development

### Challenges Faced:
- Understanding virtual environment activation
- Organizing folders correctly

### Reflection:
Today helped me understand how real backend projects are structured before actual coding begins.

Today I also learned how to navigate project directories using terminal commands like ls and cd to verify project structure.


Today I reset my MySQL root password safely using MySQL Workbench and understood how database authentication works in backend integration.


Today I designed and created the relational schema for my Event Management System.

I implemented:
- Primary Keys
- Foreign Keys
- ON DELETE CASCADE
- A junction table to resolve a many-to-many relationship

This helped me understand referential integrity and schema design.


Today I successfully connected Flask to MySQL and launched my backend server locally.
Seeing the server run at http://127.0.0.1:5000 confirmed that my application layer is properly integrated with the database.

## Rendering Frontend via Flask

Today I successfully connected my HTML frontend with Flask backend using the render_template() function.

I understood:
- How Flask routes map URLs to functions
- How templates folder is automatically recognized
- How backend returns HTML instead of plain text

This marked the full integration of the presentation layer in my 3-tier architecture.

## Day 1 – Backend & Database Integration Completed

Today I successfully:

- Set up a Flask project structure
- Created a MySQL relational schema
- Implemented primary and foreign keys
- Connected Flask backend to MySQL
- Rendered my first HTML template

This session helped me understand how a 3-tier web architecture works in practice.

## Implemented Student Registration

Today I implemented a complete registration system.

Key concepts learned:
- Handling HTTP GET and POST methods
- Accessing form data using request.form
- Writing parameterized SQL queries
- Committing transactions in MySQL
- Understanding execution order in Flask (app.run() must be last)

Successfully verified data insertion in the students table.









## 📝 Introduction

When I started building the Event Management System, I thought it would be a simple project involving login pages and event tables. However, as I progressed, I realized that developing even a small web application requires careful planning, debugging, UI improvements, and logical structuring.

This project helped me understand how frontend design and backend logic work together to create a smooth user experience.

---

## 🚀 Initial Development Phase

In the beginning, I focused on setting up:

* Home page
* Login and Register pages
* Admin and Student roles
* Database connection

At first, I kept the system simple. But I soon noticed that the login flow was not structured properly. The user had to select a role multiple times, which made the experience confusing.

This made me understand how important user flow design is in web applications.

---

## 🔄 Improving Role-Based Login

One major learning moment was restructuring the login process.

Originally:
Home → Login → Select Role → Login → Select Role again

This duplication made the system messy.

So I redesigned it as:
Home → Login → Select Role (centered UI) → Direct login form (based on role)

This improved both logic clarity and user experience. I learned how to pass role parameters in URLs and control rendering accordingly in Flask.

---

## 🛠 Debugging Challenges

I encountered several issues such as:

* 404 Not Found errors
* Invalid route handling
* Plain text error messages for invalid credentials
* Buttons appearing as simple links

Instead of ignoring them, I fixed them properly by:

* Checking route definitions in `app.py`
* Redirecting correctly after login
* Styling error messages inside templates
* Converting plain links into styled buttons

This taught me that debugging is not just fixing errors — it is understanding why the error happened.

---

## 🎨 UI/UX Enhancements

After the backend was stable, I focused on design.

I transformed:

* Plain tables → Styled soft pastel cards
* Simple links → Rounded pastel buttons
* Dashboard text → Card-style layout
* Error messages → Styled feedback alerts

I experimented with soft glam, Pinterest-inspired pastel UI themes.

Through this, I learned:

* The importance of consistency in design
* How CSS transitions and hover effects enhance professionalism
* How small UI improvements drastically improve user perception

---

## 📊 Event and Registration Logic

I implemented:

* Admin event creation (with date, venue, seats, theme, requirements)
* Student event registration form
* Seat tracking logic
* Prevention of duplicate registrations
* Viewing registered events

This helped me understand:

* Database relationships
* Conditional checks before inserting data
* Managing state through sessions

---

## 🧠 Key Learnings

From this project, I learned:

1. Planning user flow is as important as writing code.
2. Clean routing prevents many logical errors.
3. UI design affects usability significantly.
4. Debugging improves understanding of the framework.
5. Small structured changes make systems more scalable.

---

## 💭 Personal Reflection

This project was not just about coding — it was about thinking like a developer.

There were moments where:

* Pages broke
* Routes failed
* UI looked too plain
* Login logic felt messy

But instead of stopping, I improved each part step by step.

By the end, I felt more confident handling:

* Flask routing
* Templates
* Role-based authentication
* CSS styling
* Logical flow design

I now understand how frontend and backend must work together seamlessly.



## 🎯 Conclusion

Developing this Event Management System helped me gain practical experience in full-stack web development. It strengthened my problem-solving ability and improved my understanding of user experience design.

More importantly, it taught me patience and structured thinking.

This project reflects both my technical growth and my ability to refine a system through continuous improvement.

---

## 🔐 Advanced Authentication — JWT & Google OAuth

### What I Implemented:

After completing the core features, I upgraded the authentication system to use industry-standard security practices.

#### JWT (JSON Web Tokens)
- Replaced Flask `session`-based authentication with stateless JWT tokens
- JWT tokens are signed with a secret key using the HS256 algorithm
- Tokens carry the user's `user_id`, `user_name`, and `role` (student/admin) inside the payload
- Tokens expire after 24 hours for security
- Tokens are stored in HTTP-only cookies, making them inaccessible to JavaScript (XSS protection)
- Built helper functions: `create_jwt()`, `verify_jwt()`, and `get_current_user()` to keep auth logic clean and reusable

#### Google OAuth 2.0
- Integrated Google OAuth using the `authlib` library
- Students can now log in using their Google account — no password needed
- Implemented the full OAuth flow:
  - `/google_login` → redirects to Google's consent screen
  - `/google_callback` → receives the authorization code, exchanges it for user info, issues a JWT
- Auto-creates a student account on first Google login using the user's Google name and email
- Used `127.0.0.1` instead of `localhost` to avoid Chrome's Private Network Access security block

### Key Concepts Understood:

- **JWT structure**: `header.payload.signature` — the payload is base64 encoded, not encrypted, so sensitive data should never be stored inside it
- **Stateless auth**: the server doesn't need to store session data — the token itself is the proof of identity
- **OAuth vs password login**: OAuth delegates identity verification to a trusted third party (Google), eliminating the need to store or manage passwords for those users
- **HTTP-only cookies**: prevent client-side JavaScript from reading the token, protecting against XSS attacks
- **redirect_uri_mismatch**: learned that the redirect URI in code must exactly match what is registered in Google Cloud Console — any mismatch blocks the OAuth flow
- **Chrome's Private Network Access**: Chrome blocks redirects from external sites (like Google) to `localhost` — using `127.0.0.1` bypasses this restriction
- **OAuth consent screen & test users**: apps in Testing mode on Google Cloud only allow explicitly added test users to authenticate

### Challenges Faced & How I Fixed Them:

| Problem | Fix |
|---|---|
| `redirect_uri_mismatch` error | Registered exact URI `http://127.0.0.1:5000/google_callback` in Google Cloud Console |
| Chrome blocking redirect to localhost | Switched all OAuth URIs from `localhost` to `127.0.0.1` |
| Google blocking login | Added email as a Test User in OAuth consent screen |
| `utcnow()` deprecation warning | Replaced with `datetime.now(datetime.timezone.utc)` |

### Reflection:

This phase pushed me beyond CRUD operations into real-world security architecture. Understanding how JWT and OAuth work — not just how to use them — gave me a much deeper appreciation for how modern web apps handle authentication. The debugging process (redirect errors, Chrome restrictions, consent screen setup) taught me that integrating third-party services requires careful attention to configuration, not just code.

---

## 🏛 Database Expansion — Venues, Organisers, Permissions & Guest RSVPs

### What I Implemented:

After completing authentication, I expanded the database schema and added four new real-world features to the system.

#### 1. Venues Table
- Created a dedicated `venues` table with `venue_name`, `location`, and `capacity` columns
- Added `venue_id` as a foreign key in the `events` table (replacing the old free-text venue field)
- Admin can add and delete venues from a dedicated `/venues` management page
- Event creation now uses a dropdown to select from registered venues
- Used `COALESCE(venues.venue_name, events.venue)` in SQL queries for backward compatibility with older events

#### 2. Organiser Per Event
- Added an `organiser` column to the `events` table
- Admin specifies the organiser name when creating an event
- Organiser is displayed in the admin events table and on the public RSVP page

#### 3. Permissions Table
- Created a `permissions` table with per-admin boolean flags: `can_create_event`, `can_delete_event`, `can_edit_event`, `can_view_registrations`
- Built a `get_admin_permissions()` helper function that reads permissions from the DB for any admin username
- Admin dashboard hides the "Create Event" card if the logged-in admin doesn't have that permission
- Admin events table conditionally shows/hides Edit, Delete, and View Registration links based on permissions
- Admin can manage permissions for any username at `/permissions` using an `ON DUPLICATE KEY UPDATE` upsert query

#### 4. Guest RSVPs
- Created an `rsvps` table storing guest name, email, phone, attendance status, and timestamp
- Public RSVP page at `/rsvp/<event_id>` — no login required, shareable link
- Guests choose "Attending" or "Not Attending" and submit their details
- Admin can view all RSVPs per event at `/admin/event/<id>/rsvps`
- Dashboard shows total RSVP count as a stat card

### Key Concepts Understood:

- **Foreign keys with ON DELETE CASCADE**: when an event is deleted, all its RSVPs are automatically removed — referential integrity enforced at the DB level
- **ON DELETE SET NULL**: when a venue is deleted, `venue_id` in events becomes NULL rather than deleting the event — preserving event data
- **COALESCE()**: SQL function that returns the first non-NULL value — used to gracefully fall back to old text venue data for existing events
- **Upsert (INSERT ... ON DUPLICATE KEY UPDATE)**: insert a row if it doesn't exist, or update it if it does — used for permissions management
- **Role-based UI rendering**: the same dashboard template shows different options depending on what permissions the admin has — separating data access (backend) from UI visibility (frontend)
- **Public vs protected routes**: RSVP pages have no auth guard — any guest can access them, unlike all other routes which require JWT

### Challenges Faced & How I Fixed Them:

| Problem | Fix |
|---|---|
| `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` not supported in MySQL 5.x | Checked existing columns first, then ran plain `ALTER TABLE ADD COLUMN` |
| Background MySQL commands hanging | Switched to foreground execution with `MYSQL_PWD` env variable instead of `-p` flag |
| Old events had no `venue_id`, causing NULL in table | Used `COALESCE(venues.venue_name, events.venue)` to show old text venue as fallback |
| Permissions needed insert-or-update behaviour | Used `INSERT ... ON DUPLICATE KEY UPDATE` (upsert) instead of separate SELECT + UPDATE |

### Reflection:

This phase taught me how real-world applications grow beyond a single table. Every new feature required thinking about how tables relate to each other, what happens when data is deleted, and how to keep old data valid while adding new structure. The permissions system in particular showed me how the same backend data can drive completely different UI experiences for different users — a pattern used in almost every production web application.



