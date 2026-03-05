# Event Bliss 🎉

A comprehensive **Flask-based event management system** that enables students to discover, register for, and manage events while providing administrators with powerful tools to create and manage events.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Database Configuration](#database-configuration)
- [Usage](#usage)
- [API Routes](#api-routes)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)

---

## Overview

Event Bliss is a full-stack web application designed to manage events efficiently. It supports two roles:

- **Students**: Can register for events, view available events, and manage their registrations
- **Admins**: Can create, edit, delete events, and view registration details

The application features:
- ✅ Role-based authentication & authorization
- ✅ Secure session management
- ✅ Real-time seat availability tracking
- ✅ Comprehensive error handling
- ✅ Responsive web interface

---

## Features

### 🎓 Student Features
- **User Registration**: Create an account with email validation
- **Authentication**: Secure login with email and password
- **Event Discovery**: Browse all available events with seat availability
- **Event Registration**: Register for events with detailed information form
- **My Events**: View all registered events in one place
- **Dashboard**: Personalized dashboard with user information

### 👨‍💼 Admin Features
- **Admin Authentication**: Secure admin login
- **Event Management**: Create, edit, and delete events
- **Event Analytics**: View total events, students, and registrations
- **Event Details**: Manage event information (name, date, time, venue, seats, theme)
- **Registration Tracking**: View all students registered for each event
- **Capacity Management**: Set maximum seats and track remaining availability

### 🔒 Security Features
- Session-based authentication
- Password-protected accounts
- Duplicate registration prevention
- Admin-only access to admin features
- Comprehensive error handling with custom error pages

---

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| **Flask** | Web framework |
| **Python 3** | Backend language |
| **MySQL** | Database |
| **HTML/CSS** | Frontend templates |
| **Flask-Mail** | Email notifications |
| **mysql-connector-python** | Database driver |

---

## Project Structure

```
event_management_project/
├── app.py                          # Main Flask application
├── README.md                        # This file
├── features_scope.md               # Project scope & planned features
├── GIT_GITHUB_LEARNING_GUIDE.md   # Git learning guide
├── static/
│   ├── style.css                   # Main stylesheet
│   └── error.css                   # Error page styling
├── templates/
│   ├── home.html                   # Homepage
│   ├── register.html               # Student registration
│   ├── login.html                  # Login page
│   ├── select_role.html            # Role selection
│   ├── student_login.html          # Student login
│   ├── admin.html                  # Admin login
│   ├── dashboard.html              # Student dashboard
│   ├── events.html                 # Events listing
│   ├── event_registration_form.html # Registration form
│   ├── my_events.html              # Student's registered events
│   ├── create_event.html           # Create new event (admin)
│   ├── edit_event.html             # Edit event (admin)
│   ├── admin_dashboard.html        # Admin dashboard
│   ├── admin_events.html           # Admin event management
│   ├── admin_event.html            # View event registrations
│   └── errors/
│       ├── 400.html                # Bad request
│       ├── 401.html                # Unauthorized
│       ├── 403.html                # Forbidden
│       ├── 404.html                # Not found
│       ├── 409.html                # Conflict (duplicate registration)
│       └── 500.html                # Server error
└── venv/                           # Virtual environment
```

---

## Installation & Setup

### Prerequisites
- Python 3.7+
- MySQL Server
- Git

### Step 1: Clone the Repository

```bash
git clone https://github.com/Rushithaborra/event_bliss.git
cd event_bliss
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install flask flask-mail mysql-connector-python
```

### Step 4: Configure Database

Update the database connection in `app.py`:

```python
db = mysql.connector.connect(
    host="localhost",
    user="your_mysql_username",
    password="your_mysql_password",
    database="event_management"
)
```

### Step 5: Create Database & Tables

Run these SQL queries in MySQL:

```sql
CREATE DATABASE event_management;
USE event_management;

-- Students table
CREATE TABLE students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL
);

-- Events table
CREATE TABLE events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    venue VARCHAR(200) NOT NULL,
    max_seats INT NOT NULL,
    theme VARCHAR(100),
    requirements TEXT
);

-- Registrations table
CREATE TABLE registrations (
    registration_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    event_id INT NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    year INT,
    dept VARCHAR(100),
    section VARCHAR(50),
    roll_no VARCHAR(50),
    phone VARCHAR(15),
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);
```

### Step 6: Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

---

## Database Configuration

### Students Table
Stores student information and credentials.

| Field | Type | Description |
|-------|------|-------------|
| student_id | INT (PK) | Unique identifier |
| name | VARCHAR(100) | Student's full name |
| email | VARCHAR(100) | Email (unique) |
| password | VARCHAR(100) | Login password |

### Events Table
Contains all event information.

| Field | Type | Description |
|-------|------|-------------|
| event_id | INT (PK) | Unique identifier |
| event_name | VARCHAR(200) | Event name |
| event_date | DATE | Event date |
| event_time | TIME | Event time |
| venue | VARCHAR(200) | Event location |
| max_seats | INT | Total available seats |
| theme | VARCHAR(100) | Event theme |
| requirements | TEXT | Event requirements |

### Registrations Table
Tracks student registrations for events.

| Field | Type | Description |
|-------|------|-------------|
| registration_id | INT (PK) | Unique identifier |
| student_id | INT (FK) | Reference to student |
| event_id | INT (FK) | Reference to event |
| first_name | VARCHAR(100) | First name |
| middle_name | VARCHAR(100) | Middle name |
| last_name | VARCHAR(100) | Last name |
| year | INT | Academic year |
| dept | VARCHAR(100) | Department |
| section | VARCHAR(50) | Section |
| roll_no | VARCHAR(50) | Roll number |
| phone | VARCHAR(15) | Contact number |
| registration_date | TIMESTAMP | Registration time |

---

## Usage

### 👨‍🎓 As a Student

1. **Register** on the homepage
2. **Login** with your credentials
3. **Browse Events** to see available events and remaining seats
4. **Register** for an event by filling the registration form
5. **View My Events** to see all registered events
6. **Logout** when done

**Demo Credentials** (if pre-created):
- Email: `student@example.com`
- Password: `password123`

### 👨‍💼 As an Admin

1. **Login** with admin credentials
2. Navigate to **Admin Dashboard** to view statistics
3. **Create Event** by filling in event details
4. **Manage Events** - Edit or delete events
5. **View Registrations** for each event
6. **Monitor Capacity** - Track seat availability

**Demo Admin Credentials**:
- Username: `admin`
- Password: `admin123`

---

## API Routes

### Public Routes
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Homepage |
| GET/POST | `/register` | Student registration |
| GET/POST | `/login` | Login page with role selection |
| GET/POST | `/select_role` | Role selection page |

### Student Routes
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/dashboard` | Student dashboard |
| GET | `/events` | Browse all events |
| GET/POST | `/register_event/<event_id>` | Register for event |
| GET | `/my_events` | View registered events |
| GET | `/logout` | Logout |

### Admin Routes
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/admin_dashboard` | Admin statistics dashboard |
| GET | `/admin_events` | List all events |
| GET/POST | `/create_event` | Create new event |
| GET/POST | `/edit_event/<event_id>` | Edit event |
| GET | `/delete_event/<event_id>` | Delete event |
| GET | `/admin/event/<event_id>` | View event registrations |

### Error Handling
| Code | Route | Description |
|------|-------|-------------|
| 400 | `/errors/400.html` | Bad request |
| 401 | `/errors/401.html` | Unauthorized |
| 403 | `/errors/403.html` | Forbidden |
| 404 | `/errors/404.html` | Not found |
| 409 | `/errors/409.html` | Conflict (duplicate registration) |
| 500 | `/errors/500.html` | Server error |

---

## Future Enhancements

Based on the project scope, the following features are planned:

### 🗓️ Venue Management
- [ ] Multiple venues database
- [ ] Venue capacity and facilities
- [ ] Venue availability tracking

### 👥 Event Organizers
- [ ] Assign organizers to events
- [ ] Organizer dashboard
- [ ] Event-specific permissions

### 🔐 Advanced Authentication
- [ ] OAuth 2.0 integration
- [ ] JWT tokens
- [ ] Role-based access control (RBAC)
- [ ] Password encryption

### 📧 Guest Management
- [ ] RSVP system
- [ ] Guest list tracking
- [ ] Email notifications
- [ ] Calendar integration

### ✔️ Validation & Error Handling
- [ ] Enhanced form validation
- [ ] Database-level constraints
- [ ] Standardized error response format
- [ ] Detailed error codes

### 📊 Analytics & Reporting
- [ ] Event attendance reports
- [ ] Registration trends
- [ ] Participant demographics
- [ ] Export to CSV/PDF

---

## Security Considerations

⚠️ **Current Implementation Notes**:
- Passwords stored in plaintext (use hashing like `bcrypt` in production)
- Hardcoded admin credentials (use environment variables)
- Session keys should be stronger (use environment variables)
- HTTPS should be enabled in production

### Recommended Improvements
1. Hash passwords using `werkzeug.security`
2. Use environment variables for sensitive data
3. Implement CSRF protection
4. Add rate limiting
5. Use HTTPS in production
6. Implement proper logging

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is open source and available under the MIT License.

---

## Author

**Rushitha Borra**

- GitHub: [@Rushithaborra](https://github.com/Rushithaborra)
- Repository: [Event Bliss](https://github.com/Rushithaborra/event_bliss)

---

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Last Updated**: March 5, 2026

Happy Event Managing! 🚀
