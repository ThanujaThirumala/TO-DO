from click import password_option
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date, datetime
import os

app = Flask(__name__)
#app.config['SECRET_KEY'] = "supersecret"
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-local-testing')
#app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///todo.db"
database_url = os.environ.get('DATABASE_URL')

if database_url :
    if database_url.startswith("postgres://"):
        # Handle the legacy prefix
        db_uri = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://"):
        # Handle the standard prefix
        db_uri = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        # Fallback for unexpected format
        db_uri = database_url
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,  # Recycle connections every 5 minutes
    }
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///todo.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# app.py (Replace your existing models with these)

# --- MODELS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    # FIX: Added server_default to ensure PostgreSQL sets the creation time automatically
    date_created = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    tasks = db.relationship('Task', backref='author', lazy=True)
    posts = db.relationship('BlogPost', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.id}')"

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)
    # FIX: Added server_default
    #date_created = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    #user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"<Task {self.id} - {self.content}>"

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # FIX: Added server_default
    date_posted = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"



# ----------------- ROUTES -----------------

# app.py (Add these new routes)

@app.route("/about")
def about():
    # Renders a simple 'about.html' template
    return render_template("about.html")

@app.route("/privacy")
def privacy():
    # Renders a simple 'privacy.html' template for the Privacy Policy
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    # Renders a simple 'terms.html' template for the Terms of Service
    return render_template("terms.html")

# app.py (Add this new route)

@app.route("/")
def home():
    if current_user.is_authenticated:
        # If logged in, go straight to their tasks
        return redirect(url_for("tasks"))
    else:
        # If logged out, prompt them to login/signup
        return redirect(url_for("signup"))

'''@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        raw_password = request.form["password"]

        if len(raw_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for("signup"))
        # Check if user/email already exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already in use. Please choose another.", "danger")
            return redirect(url_for("signup"))
        password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")
        user = User(username=username, email=email, password=password_option)
        db.session.add(user)
        db.session.commit()
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")'''


# app.py (Around line 85)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("tasks"))
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        # FIX: Ensure we generate the hash and store the resulting UTF-8 string.
        # This line is correct, but reconfirming its place in the code structure.
        hashed_password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")

        user = User(username=username, email=email, password=hashed_password) # Use the new variable
        # Check if user already exists (Good practice)
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already taken.", "danger")
            return render_template("signup.html")
        try:
            user = User(username=username, email=email, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Signup successful! Welcome!", "success")
            return redirect(url_for("tasks"))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred during signup: {e}", "danger")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Already logged in? Go to tasks.
        return redirect(url_for("tasks"))
    
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("tasks"))
        else:
            flash("Login failed. Check email and password.", "danger")

    return render_template("login.html")


@app.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():
    if request.method == "POST":
        content = request.form["content"]
        due_date_str = request.form.get("due_date") # Get due date from form
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'danger')
                return redirect(url_for('tasks'))
            
        if not content:
            flash("Task content cannot be empty!", "danger")
            return redirect(url_for("tasks"))
        
        new_task_due_date = None
        if due_date_str:
            try:
                new_task_due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid due date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("tasks"))

        new_task = Task(content=content, user_id=current_user.id, due_date=new_task_due_date)

        try:
            db.session.add(new_task)
            db.session.commit()
            flash("Task added successfully!", "success")
            return redirect(url_for("tasks"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding task: {e}", "danger")
            return redirect(url_for("tasks"))
    
    else: 
        # 1. Start with the base query: incomplete tasks for the current user
        query = Task.query.filter_by(user_id=current_user.id, completed=False)
        completed_tasks = Task.query.filter_by(user_id=current_user.id, completed=True).order_by(Task.created_at.desc()).all()
        
        filter_type = request.args.get('filter')
        today = date.today()
        
        # 2. APPLY FILTERING to the 'query' object
        if filter_type == 'today':
            # Only tasks due today
            query = query.filter(Task.due_date == today)
            flash("Showing tasks due today.", "info")
            
        elif filter_type == 'overdue':
            # Only tasks with a due date in the past
            query = query.filter(Task.due_date < today)
            flash("Showing overdue tasks.", "warning")
            
        elif filter_type == 'pending':
             # Only tasks with a future due date
            query = query.filter(Task.due_date > today)
            flash("Showing pending tasks.", "info")

        # 3. EXECUTE THE FINAL QUERY and apply sorting
        # This uses the 'query' object, which has been filtered if filter_type was set.
        incomplete_tasks = query.order_by(Task.due_date.asc(), Task.created_at.desc()).all()
        return render_template("tasks.html", incomplete_tasks=incomplete_tasks, completed_tasks=completed_tasks,date=date)

@app.route("/complete/<int:id>")
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)
    task.completed = True
    db.session.commit()
    return redirect(url_for("tasks"))

# app.py, new route or modify complete_task
@app.route("/toggle/<int:id>")
@login_required
def toggle_task(id):
    task = Task.query.get_or_404(id)
    # Toggle the 'completed' status
    task.completed = not task.completed
    db.session.commit()
    flash("Task status updated.", "info")
    return redirect(url_for("tasks"))

@app.route("/edit/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_task(id):
    task = Task.query.get_or_404(id)
    
    if request.method == 'POST':
        task.content = request.form['content']
        due_date_str = request.form.get("due_date")
        
        new_task_due_date = None
        if due_date_str:
            try:
                # Convert string 'YYYY-MM-DD' from HTML input to a Python date object
                new_task_due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid due date format.", "danger")
                return redirect(url_for('edit_task', id=task.id))
        
        task.due_date = new_task_due_date
        
        try:
            db.session.commit()
            flash("Task updated successfully!", "success")
            return redirect(url_for('tasks'))
        except Exception:
            db.session.rollback()
            flash("Error updating task.", "danger")
            return redirect(url_for('tasks'))

    # GET request: Show the edit form
    return render_template('edit_task.html', task=task)

@app.route("/delete/<int:id>")
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("tasks"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

# ----------------- MAIN -----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("🚀 Starting Flask server...")
    app.run(debug=True)








