from helpers import apology, login_required
from flask import Flask, flash, render_template, request, redirect, g, session
import sqlite3
import os
from werkzeug.utils import secure_filename

from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

app.secret_key = 'this is secret key'


app.config['UPLOAD_FOLDER'] = 'static/img/books'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Connect to SQLite database
conn = sqlite3.connect('bookstore.db')
cursor = conn.cursor()

# Create tables
cursor.execute('''
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY,
        title TEXT UNIQUE NOT NULL,
        author TEXT NOT NULL,
        price REAL NOT NULL,
        photoname TEXT UNIQUE NOT NULL, 
        genre TEXT NOT NULL,
        stocks INTEGER NOT NULL,
        ratings REAL NOT NULL,
        publisher TEXT,
        description TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        hash TEXT NOT NULL,
        preferredGenre1 TEXT NOT NULL,
        preferredGenre2 TEXT NOT NULL,
        preferredGenre3 TEXT NOT NULL
    )
''')


"""
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cart(
        id INTEGER PRIMARY KEY,
        bookname TEXT NOT NULL,
        bookprice REAL NOT NULL,
        FOREIGN KEY (bookname) REFERENCES books(name),
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),        
        quantity INTEGER
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_amount REAL NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER,
        book_id INTEGER,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (book_id) REFERENCES books(id)
    )
''')

"""


conn.commit()



# Function to get the database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('bookstore.db')
    return db


# Teardown function to close the database connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()




# Route to homepage
@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books ORDER BY ratings DESC LIMIT 4" )
    books = cursor.fetchall()
    
    cursor.execute("SELECT * FROM books ORDER BY id DESC LIMIT 4")
    newest = cursor.fetchall()
    
    recommended = []  # Initialize as an empty list

    if "user_id" in session:
        cursor.execute("SELECT preferredGenre1, preferredGenre2, preferredGenre3 FROM users WHERE id=?", (session["user_id"],))
        preferred = cursor.fetchone()  # Use fetchone() instead of fetchall()
        
        if preferred:
            # Fetch a limited number of books for each preferred genre and extend the recommended list
            cursor.execute("SELECT * FROM books WHERE genre=? LIMIT 2", (preferred[0],))
            rows = cursor.fetchall()
            recommended.extend(rows)
            
            cursor.execute("SELECT * FROM books WHERE genre=? LIMIT 1", (preferred[1],))
            rows = cursor.fetchall()
            recommended.extend(rows)
            
            cursor.execute("SELECT * FROM books WHERE genre=? LIMIT 1", (preferred[2],))
            rows = cursor.fetchall()
            recommended.extend(rows)
    
    return render_template("index.html", books=books, newest=newest, recommended=recommended)


@app.route("/product/<int:book_id>")
def product(book_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    product = cursor.fetchone() 
    cursor.execute("SELECT * FROM books WHERE genre = ? EXCEPT SELECT * FROM books WHERE id = ? LIMIT 4", (product[5], product[0],))
    books = cursor.fetchall()
    return render_template('product.html', product=product, books=books)


# Route to all books page
@app.route("/books")
def books():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books")
    books = cursor.fetchall()
    return render_template("books.html", books=books)


@app.route("/cart")
@login_required
def cart():
    return render_template("cart.html")


"""Register user"""
@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password and confirm password", 400)

        elif not (request.form.get("preference1")) or not (request.form.get("preference2")) or not (request.form.get("preference1")):
            return apology("must select all the preferences", 400)

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if password != confirmation:
            return apology("both passwords do not match", 400)

        elif (len(password) < 8):
            return apology("Weak password. Try a different one!", 400)

        conn = get_db()
        cursor = conn.cursor()
        # Query database for username
        username = request.form.get("username")
        cursor.execute("SELECT * FROM users WHERE name = ?", (username,))
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 0:
            return apology("username already exists. Try a different one!", 400)
        genre1 = request.form.get("preference1")
        genre2 = request.form.get("preference2")
        genre3 = request.form.get("preference3")

        # Inserting new user's data into database
        cursor.execute('''
                       INSERT INTO users (name, hash, preferredGenre1, preferredGenre2, preferredGenre3) VALUES (?, ?, ?, ?, ?)
                       ''', (username, generate_password_hash(password), genre1, genre2, genre3))
        
        conn.commit()
        conn.close()

        flash("User Registered!")
        return redirect("/")

    else:
        return render_template("signup.html")



"""Log user in"""
@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        conn = get_db()
        cursor = conn.cursor()
        username = request.form.get("username")
        cursor.execute("SELECT * FROM users WHERE name = ?", (username,)) 
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][2], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        conn.commit()
        conn.close()

        # Redirect user to home page
        flash("Welcome Back!")
        return redirect("/")

    else:
        return render_template("login.html")


"""Log user out"""
@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()
    flash("Logged out!")
    return redirect("/")


# Route for handling book uploads
@app.route('/admin', methods=["GET", "POST"])
def admin():
    if request.method == 'GET':
        return render_template('admin.html')
    else:
        #if 'image' or 'title' or 'author' or 'price' not in request.files:
        #    return redirect(request.url)

        file = request.files['image']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            title = request.form.get('title')
            author = request.form.get('author')
            price_str = request.form.get('price')
            photoname = filename
            genre = request.form.get('genre')
            stocks = request.form.get('stocks')
            ratings = request.form.get('ratings')
            publisher = request.form.get('publisher')
            description = request.form.get('description')

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO books (title, author, price, photoname, genre, stocks, ratings, publisher, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, author, price_str, photoname, genre, stocks, ratings, publisher, description))

            conn.commit()
            conn.close()

            flash("Book uploaded successfully!")
            return redirect('/')
        

if __name__ == "__main__":
    app.run(debug=True)
