# Git & GitHub Learning Guide - Event Management Project

Welcome! This guide teaches you Git and GitHub using your Flask event management project as a real-world example.

---

## Table of Contents
1. [Git Basics](#git-basics)
2. [Prerequisites](#prerequisites)
3. [Initializing Your Project with Git](#initializing-your-project-with-git)
4. [Essential Git Workflows](#essential-git-workflows)
5. [GitHub Setup](#github-setup)
6. [Collaboration Workflows](#collaboration-workflows)
7. [Common Git Commands Reference](#common-git-commands-reference)
8. [Troubleshooting](#troubleshooting)

---

## Git Basics

### What is Git?
Git is a **version control system** that tracks changes to your code. Think of it as a "save system" for your entire project where you can:
- Save versions of your code (commits)
- Go back to previous versions (rollback)
- See what changed and when
- Collaborate with others

### What is GitHub?
GitHub is a **cloud platform** that hosts Git repositories, enabling you to:
- Store your code online (backup)
- Collaborate with team members
- Track issues and features
- Share your code publicly

### Key Concepts
- **Repository (Repo)**: Your project folder tracked by Git
- **Commit**: A snapshot of your code at a point in time
- **Branch**: A parallel version of your code
- **Remote**: A server copy of your repo (like GitHub)
- **Working Directory**: Your local folder where you make changes
- **Staging Area**: Where you prepare changes before committing

---

## Prerequisites

### Install Git
Check if Git is installed:
```bash
git --version
```

If not installed, download from https://git-scm.com

### Configure Git (first time only)
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Verify:
```bash
git config --global user.name
git config --global user.email
```

---

## Initializing Your Project with Git

### Step 1: Initialize Git in Your Project

Navigate to your project directory:
```bash
cd /Users/rushithaborra/Desktop/event_management_project
```

Initialize Git:
```bash
git init
```

This creates a hidden `.git` folder that stores all version history.

### Step 2: Create a `.gitignore` File

Create a `.gitignore` file to exclude files you don't want tracked (like passwords, virtual environments):

Create file `.gitignore`:
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp

# Database & Credentials
*.db
*.sqlite
.env
config.py

# Flask
instance/
.webassets-cache

# OS
.DS_Store
.DS_Store?

# Logs
*.log
```

### Step 3: Stage Your Files

See what's untracked:
```bash
git status
```

Add all files to staging area:
```bash
git add .
```

Or add specific files:
```bash
git add app.py
git add templates/
```

See staged changes:
```bash
git status
```

### Step 4: Make Your First Commit

```bash
git commit -m "Initial commit: Event management project structure"
```

The message explains what changed. Good commit messages are important!

### View Commit History
```bash
git log
git log --oneline  # Shorter format
```

---

## Essential Git Workflows

### Workflow 1: Making Changes (Daily Work)

**Scenario**: You fixed a bug in the login page.

```bash
# 1. See what changed
git status

# 2. View the actual changes
git diff templates/login.html

# 3. Stage the changes
git add templates/login.html

# 4. Commit with a descriptive message
git commit -m "Fix: Correct password validation in login form"

# 5. View the history
git log --oneline
```

### Workflow 2: Undoing Changes

**Undo changes before staging:**
```bash
git restore templates/login.html
```

**Unstage a file (keep changes):**
```bash
git restore --staged app.py
```

**Undo the last commit (keep changes):**
```bash
git reset --soft HEAD~1
```

**Undo the last commit (discard changes):**
```bash
git reset --hard HEAD~1
```

### Workflow 3: Working with Branches

Branches let you work on features separately.

**Create a new branch for a feature:**
```bash
git branch feature/student-dashboard
```

**List branches:**
```bash
git branch
```

**Switch to the branch:**
```bash
git checkout feature/student-dashboard
```

Or create and switch in one command:
```bash
git checkout -b feature/student-dashboard
```

**Make changes and commits on this branch:**
```bash
git add templates/dashboard.html
git commit -m "Add event filtering to student dashboard"
```

**Switch back to main:**
```bash
git checkout main
```

**Merge the feature branch into main:**
```bash
git merge feature/student-dashboard
```

**Delete the branch (after merging):**
```bash
git branch -d feature/student-dashboard
```

### Understanding Branches with Your Project

```
main (stable code)
├── feature/student-dashboard (work in progress)
├── bugfix/login-validation (fixing a bug)
└── feature/email-notifications (another feature)
```

---

## GitHub Setup

### Step 1: Create a GitHub Account
1. Go to https://github.com
2. Sign up with your email
3. Verify your email

### Step 2: Create a New Repository on GitHub
1. Click the **+** icon → **New repository**
2. Name: `event_management_project`
3. Add description: "Flask-based event management system"
4. Choose **Public** or **Private**
5. Click **Create repository**

Don't initialize with README (you already have files).

### Step 3: Connect Local Repo to GitHub

GitHub shows you the commands. Run these in your project folder:

```bash
# Add GitHub as remote (origin is the default name)
git remote add origin https://github.com/YOUR_USERNAME/event_management_project.git

# Rename branch to main (if it's not already)
git branch -M main

# Push your code to GitHub
git push -u origin main
```

The `-u` flag sets up tracking (future pushes don't need the branch name).

### Step 4: Verify on GitHub
Visit `https://github.com/YOUR_USERNAME/event_management_project` - your code should be there!

---

## Collaboration Workflows

### Workflow 1: Push Changes to GitHub

After committing locally:
```bash
git push origin main
```

Check what's on GitHub vs local:
```bash
git status
```

### Workflow 2: Pull Changes from GitHub

If someone else (or you on another computer) made changes:
```bash
git pull origin main
```

This is equivalent to:
```bash
git fetch origin main    # Download changes
git merge origin/main    # Merge into local
```

### Workflow 3: Feature Branch Workflow (Team)

Perfect for teams working on different features:

**On your local machine:**
```bash
# Create feature branch
git checkout -b feature/email-notifications

# Make changes
git add templates/event_registration_form.html
git commit -m "Add email confirmation to event registration"

# Push to GitHub
git push origin feature/email-notifications
```

**On GitHub, create a Pull Request (PR):**
1. Go to your repository on GitHub
2. Click **Pull requests** tab
3. Click **New pull request**
4. Select `feature/email-notifications` → `main`
5. Add description and click **Create pull request**

**Team reviews and merges:**
- Team members review your changes
- Add comments, request changes, or approve
- Once approved, merge the PR
- Delete the branch on GitHub

**Update your local main:**
```bash
git checkout main
git pull origin main
git branch -d feature/email-notifications
```

### Workflow 4: Syncing a Forked Repository

If you forked someone's project:

```bash
# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/event_management_project.git

# Fetch latest changes
git fetch upstream

# Merge into your main
git merge upstream/main

# Push to your fork
git push origin main
```

---

## Common Git Commands Reference

### Viewing Information
```bash
git status              # Current status
git log                 # Commit history
git log --oneline       # Shorter log
git log --graph --all   # Visual branch history
git diff                # See changes not staged
git diff --staged       # See staged changes
git show COMMIT_HASH    # See specific commit
git blame FILE.py       # See who changed each line
```

### Making Changes
```bash
git add FILE            # Stage a file
git add .               # Stage all changes
git commit -m "Message" # Commit with message
git commit --amend      # Modify last commit
```

### Undoing Changes
```bash
git restore FILE        # Discard changes in file
git restore --staged FILE  # Unstage file
git reset --soft HEAD~1 # Undo commit, keep changes
git reset --hard HEAD~1 # Undo commit, lose changes
git revert COMMIT_HASH  # Undo a commit safely (creates new commit)
```

### Branches
```bash
git branch              # List branches
git branch BRANCH_NAME  # Create branch
git checkout BRANCH     # Switch branch
git checkout -b BRANCH  # Create and switch
git merge BRANCH        # Merge branch into current
git branch -d BRANCH    # Delete branch
```

### Remote Operations
```bash
git remote -v           # List remote URLs
git remote add NAME URL # Add remote
git push origin BRANCH  # Push to GitHub
git pull origin BRANCH  # Pull from GitHub
git fetch origin        # Download without merging
```

---

## Real-World Example: Adding a Feature

Let's say you want to add an "email notifications" feature to your event management system.

### Day 1: Start Feature
```bash
# Update main from GitHub
git pull origin main

# Create feature branch
git checkout -b feature/email-notifications

# Make changes
# ... edit templates/event_registration_form.html
# ... modify app.py to add email logic

# Check what changed
git status
git diff app.py

# Stage and commit
git add app.py templates/event_registration_form.html
git commit -m "Feature: Add email notifications to event registration"

# Push to GitHub
git push origin feature/email-notifications
```

### Day 2: Review and Merge
```bash
# On GitHub, create Pull Request and get approval

# Merge on GitHub or locally:
git checkout main
git pull origin main
git merge feature/email-notifications
git push origin main

# Cleanup
git branch -d feature/email-notifications
git push origin --delete feature/email-notifications
```

---

## Best Practices

### Commit Messages
**Good:**
```
Fix: Correct password validation in login
Feature: Add event filtering to dashboard
Docs: Update installation instructions
```

**Bad:**
```
fixed stuff
update
asdf
```

### Branch Naming
Use descriptive names:
- `feature/student-dashboard`
- `bugfix/login-validation`
- `docs/setup-instructions`
- `refactor/database-queries`

### Commit Frequency
- Small, logical commits
- Commit after completing one task
- Easy to understand history

### Before Pushing
```bash
git log --oneline -5  # Check your commits
git diff main origin/main  # Check what's different
```

---

## Troubleshooting

### "fatal: not a git repository"
You're not in a git folder. Run:
```bash
git init
```

### Merge Conflicts
When two people edit the same lines:

```bash
git merge feature/branch
# Shows: CONFLICT (content conflict)

# 1. Open the file and look for:
# <<<<<<< HEAD
# your code
# =======
# their code
# >>>>>>> feature/branch

# 2. Edit to keep what you want
# 3. Stage and commit
git add FILE
git commit -m "Resolve merge conflict"
```

### Detached HEAD
You accidentally switched to a commit instead of a branch:

```bash
git checkout main  # Go back to main
# Or save your work:
git checkout -b temp-branch  # Save to a new branch
```

### Pushed to Wrong Branch?
```bash
# Undo the push (be careful!)
git push origin main --force-with-lease

# Push to correct branch
git push origin feature/correct-branch
```

### Want to See What You'll Push?
```bash
git push --dry-run origin main
```

---

## Next Steps

1. **Initialize your project**: `git init`
2. **Create `.gitignore`**: Add ignored files
3. **Make first commit**: `git add . && git commit -m "Initial commit"`
4. **Create GitHub repo**: Follow GitHub Setup section
5. **Push to GitHub**: `git push -u origin main`
6. **Create a feature branch**: Practice branch workflow
7. **Make changes & commit**: Practice daily workflow

---

## Useful Resources

- [Git Official Docs](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Atlassian Git Tutorials](https://www.atlassian.com/git/tutorials)
- [Interactive Git Demo](https://learngitbranching.js.org/)

---

## Quick Cheat Sheet

```bash
# Setup (first time)
git config --global user.name "Your Name"
git config --global user.email "email@example.com"

# Initialize project
git init
git add .
git commit -m "Initial commit"

# Create GitHub repo and connect
git remote add origin GITHUB_URL
git branch -M main
git push -u origin main

# Daily workflow
git pull origin main             # Get latest
git checkout -b feature/NAME     # Create branch
git add .                        # Stage changes
git commit -m "Description"      # Commit
git push origin feature/NAME     # Push
# Create Pull Request on GitHub

# Merge
git checkout main
git pull origin main
git merge feature/NAME
git push origin main
```

Good luck learning Git! 🚀
