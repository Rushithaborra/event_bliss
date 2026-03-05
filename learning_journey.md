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


