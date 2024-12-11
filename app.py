from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'carat-land-2024'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db(): # Connects to the database 
    db = sqlite3.connect('database/games_review.db')
    db.row_factory = sqlite3.Row
    return db 

@app.route('/')
def home():
     # Calls the database and gets all the values in the 'games' table
    db = get_db() # Secure from SQL injection by parameterised query - https://qwiet.ai/solving-sql-injection-parameterized-queries-vs-stored-procedures/#:~:text=Parameterized%20Queries%20offer%20a%20robust,recognizes%20the%20input%20as%20data.
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('home.html', games=games) # Opens the home page template with game data
    
@app.route('/game/<int:game_id>')
def gameform(game_id):
    db = get_db() # Calls the database and gets all the values in the 'games' table with a specific ID
    game = db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    entries = db.execute(''' 
        SELECT 
            entries.*, 
            users.username 
        FROM 
            entries 
        JOIN 
            users 
        ON 
            entries.user_id = users.id 
        WHERE 
            entries.game_id = ?
        ORDER BY entries.created_at DESC
    ''', (game_id,)).fetchall() # Calls the entries to corresponding game and the associated usernames
    return render_template('gameform.html', game=game, entries=entries)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST': # Get the username and password from the form - https://stackoverflow.com/questions/10434599/get-the-data-received-in-a-flask-request
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone() # Finds the user by username; secures from SQL injection

        if user and check_password_hash(user['password'], password): # Password securely hashed
            # Save user info in session if login is successful - https://testdriven.io/blog/flask-sessions/
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success') # Output a success message 
            return redirect(url_for('home')) 
        else:
            flash('Invalid username or password', 'error') # Output a error message 
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password) # Hash the password for security; # secures passwords 

        db = get_db() # Insert/Update new user info into the database
        db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        db.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login')) # Once successful, redirects to login page
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear() # Clear the session data and refreshes to home page; secure session management
    return redirect(url_for('home'))

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('search', '').strip() # Search query from the URL - Used chatgpt
    db = get_db()

    if query:
         # Search for games by title that match the query
        games = db.execute('SELECT * FROM games WHERE title LIKE ?', ('%' + query + '%',)).fetchall()

        if not games: # Message if game is not found
            flash('Game is currently unavailable. More games will be added shortly.', 'error')
    else:
        # If no query, get all games
        games = db.execute('SELECT * FROM games').fetchall()
    return render_template('home.html', games=games)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    if 'user_id' not in session:
        # Redirect to login if the user is not logged in
        return redirect(url_for('login'))

    # Get entry details from the form
    title = request.form['title']
    game_id = request.form['game'] 
    description = request.form['description']
    rating = request.form['rating']
    image = request.files['image']

    if 'image' not in request.files or image.filename == '': # Check if an image was uploaded
        flash('No image selected', 'error')
        return redirect(url_for('gameform', game_id=game_id)) 

    if image and allowed_file(image.filename): # Check if the uploaded file is valid; # prevents file-based attacks
        # Save the image with a unique filename
        filename = secure_filename(f"{datetime.now().timestamp()}_{image.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Create the full file path
        image.save(filepath)

        db = get_db()
        # Insert the entry to the database
        db.execute('''
            INSERT INTO entries (user_id, title, game_id, description, rating, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], title, game_id, description, rating, f"uploads/{filename}"
        ))
        db.commit()

        # Calculate the average rating for the game - getting rating from the entries table
        entries = db.execute('''
            SELECT rating FROM entries WHERE game_id = ?
        ''', (game_id,)).fetchall() # Secure from SQL injection

        if entries:
            total_rating = sum(entry['rating'] for entry in entries)  # Calculate the total rating
            average_rating = round(total_rating / len(entries), 1)  # Calculate the average rating, rounded to 1 decimal place
        else:
            average_rating = 0  

        db.execute('''
            UPDATE games
            SET rating = ?
            WHERE id = ?
        ''', (average_rating, game_id)) # Update the game's average rating in the database
        db.commit()

        flash('Entry added successfully and game rating updated!', 'success')
    else:
        flash('Invalid file type', 'error') # Show an error message for invalid file types
    return redirect(url_for('gameform', game_id=game_id))  # Redirect back to the specific game's form


@app.route('/edit_entry/<int:entry_id>', methods=['POST'])
def edit_entry(entry_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        flash('You need to log in to edit an entry.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    entry = db.execute('SELECT * FROM entries WHERE id = ? AND user_id = ?', 
                        (entry_id, session['user_id'])).fetchone() # Get the entry if it exists and belongs to the logged in user
    
    # Get the updated title, description, rating from the entry form
    title = request.form['title']
    description = request.form['description']
    rating = int(request.form['rating'])

    if 'image' in request.files and request.files['image'].filename != '':
         # Check if a new image file is uploaded
        file = request.files['image']
        if allowed_file(file.filename):
            try: # Validate the uploaded file type
                old_image_path = os.path.join(app.root_path, 'static', entry['image_path'])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path) # Delete the old image if it exists
            except Exception as e:
                # Handle errors during file deletion
                print(f"Error deleting old image")

            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # Save the uploaded image.
            image_path = f"uploads/{filename}"

            # Update the database with the new entry data with image
            db.execute('''
                UPDATE entries
                SET title = ?, description = ?, rating = ?, image_path = ?
                WHERE id = ? AND user_id = ?
            ''', (title, description, rating, image_path, entry_id, session['user_id']))
        else:
            flash('Invalid file type', 'error') # Show an error if the file type is invalid
            return redirect(url_for('gameform', game_id=entry['game_id'])) 
    else:
        # Update the database with the new entry data without image
        db.execute('''
            UPDATE entries
            SET title = ?, description = ?, rating = ?
            WHERE id = ? AND user_id = ?
        ''', (title, description, rating, entry_id, session['user_id']))
    db.commit()

    # Get and recalculate the average rating for the game, then update the database
    ratings = db.execute('''
        SELECT rating FROM entries WHERE game_id = ?
    ''', (entry['game_id'],)).fetchall()
    average_rating = round(sum([r['rating'] for r in ratings]) / len(ratings), 1) if ratings else 0
    
    db.execute('''
        UPDATE games
        SET rating = ?
        WHERE id = ?
    ''', (average_rating, entry['game_id']))
    db.commit()
    flash('Entry updated successfully!', 'success')
    return redirect(url_for('gameform', game_id=entry['game_id']))

@app.route('/delete_entry/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()  # Get the entry if it exists and belongs to the logged-in user
    entry = db.execute('SELECT * FROM entries WHERE id = ? AND user_id = ?', 
                        (entry_id, session['user_id'])).fetchone()

    try: # Gte image file and delete if it exists
        image_path = os.path.join(app.root_path, 'static', entry['image_path'])
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting image file: {e}")

    # Delete the entry from the database    
    db.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
    db.commit()
    flash('Entry deleted successfully!', 'success')

    # Recalulate and update the game's average rating in the database
    ratings = db.execute('''
        SELECT rating FROM entries WHERE game_id = ?
    ''', (entry['game_id'],)).fetchall()
    average_rating = round(sum([r['rating'] for r in ratings]) / len(ratings), 1) if ratings else 0 # Round to 1 decimal place

    db.execute('''
        UPDATE games
        SET rating = ?
        WHERE id = ?
    ''', (average_rating, entry['game_id']))
    db.commit()
    return redirect(url_for('gameform', game_id=entry['game_id']))

@app.route('/offline')
def offline():
    response = make_response(render_template('offline.html'))
    return response

@app.route('/service-worker.js')
def sw():
    response = make_response(
        send_from_directory(os.path.join(app.root_path, 'static/js'), 'service-worker.js'))
    return response

@app.route('/manifest.json')
def manifest():
    response = make_response(
        send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json'))
    return response
    
if __name__ == '__main__':
    app.run(debug=True)