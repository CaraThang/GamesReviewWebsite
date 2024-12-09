from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, send_from_directory
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    db = sqlite3.connect('database/games_review.db')
    db.row_factory = sqlite3.Row
    return db

@app.route('/')
def home():
    db = get_db()
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('home.html', games=games)
    
@app.route('/game/<int:game_id>')
def gameform(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    if not game:
        flash('Game not found!', 'error')
        return redirect(url_for('home'))

    entries = db.execute('''
        SELECT * FROM entries
        WHERE game_id = ?
        ORDER BY created_at DESC
    ''', (game_id,)).fetchall()

    return render_template('gameform.html', game=game, entries=entries)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))  # Redirect to the homepage
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        db = get_db()
        db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        db.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('search', '').strip()
    db = get_db()

    if query:
        # Search for games whose title matches the query
        games = db.execute('SELECT * FROM games WHERE title LIKE ?', ('%' + query + '%',)).fetchall()

        if not games:
            flash('Game is currently unavailable. More games will be added shortly.', 'error')
    else:
        games = db.execute('SELECT * FROM games').fetchall()

    return render_template('home.html', games=games)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    title = request.form['title']
    game_id = request.form['game']  # Get the selected game ID from the hidden field
    description = request.form['description']
    rating = request.form['rating']  # Get the star rating from the form
    image = request.files['image']

    # Ensure game_id and rating are provided
    if not game_id:
        flash('Please select a game.', 'error')
        return redirect(url_for('gameform', game_id=game_id))  # Redirect to the gameform for the specific game

    if not rating:
        flash('Please provide a star rating.', 'error')
        return redirect(url_for('gameform', game_id=game_id))  # Redirect to the gameform for the specific game

    if 'image' not in request.files or image.filename == '':
        flash('No image selected', 'error')
        return redirect(url_for('gameform', game_id=game_id))  # Redirect to the gameform for the specific game

    if image and allowed_file(image.filename):
        # Generate a unique filename for the image
        filename = secure_filename(f"{datetime.now().timestamp()}_{image.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)

        db = get_db()

        # Insert data into the `entries` table, including the `rating`
        db.execute('''
            INSERT INTO entries (user_id, title, game_id, description, rating, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            title,
            game_id,
            description,
            rating,
            f"uploads/{filename}"
        ))
        db.commit()

        # Fetch all entries for the game to calculate the average rating
        entries = db.execute('''
            SELECT rating FROM entries WHERE game_id = ?
        ''', (game_id,)).fetchall()

        # Calculate the average rating
        if entries:
            total_rating = sum(entry['rating'] for entry in entries)
            average_rating = total_rating / len(entries)
        else:
            average_rating = 0  # In case there are no entries for this game yet

        # Update the game's rating in the `games` table
        db.execute('''
            UPDATE games
            SET rating = ?
            WHERE id = ?
        ''', (average_rating, game_id))
        db.commit()

        flash('Entry added successfully and game rating updated!', 'success')
    else:
        flash('Invalid file type', 'error')

    return redirect(url_for('gameform', game_id=game_id))  # Redirect back to the specific game's form


@app.route('/edit_entry/<int:entry_id>', methods=['POST'])
def edit_entry(entry_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    entry = db.execute('SELECT * FROM entries WHERE id = ? AND user_id = ?', 
                        (entry_id, session['user_id'])).fetchone()

    if not entry:
        flash('Entry not found or access denied', 'error')
        return redirect(url_for('gameform', game_id=entry['game_id']))  # Use entry['game_id'] here

    title = request.form['title']
    description = request.form['description']
    rating = int(request.form['rating'])

    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        if allowed_file(file.filename):
            try:
                old_image_path = os.path.join(app.root_path, 'static', entry['image_path'])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            except Exception as e:
                print(f"Error deleting old image: {e}")

            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_path = f"uploads/{filename}"
            db.execute('''
                UPDATE entries
                SET title = ?, description = ?, rating = ?, image_path = ?
                WHERE id = ? AND user_id = ?
            ''', (title, description, rating, image_path, entry_id, session['user_id']))
        else:
            flash('Invalid file type', 'error')
            return redirect(url_for('gameform', game_id=entry['game_id']))  # Use entry['game_id'] here
    else:
        db.execute('''
            UPDATE entries
            SET title = ?, description = ?, rating = ?
            WHERE id = ? AND user_id = ?
        ''', (title, description, rating, entry_id, session['user_id']))
    db.commit()

    # Recalculate the average rating after editing the entry
    ratings = db.execute('''
        SELECT rating FROM entries WHERE game_id = ?
    ''', (entry['game_id'],)).fetchall()
    average_rating = sum([r['rating'] for r in ratings]) / len(ratings) if ratings else 0

    # Update the average rating in the `games` table
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
    
    db = get_db()
    entry = db.execute('SELECT * FROM entries WHERE id = ? AND user_id = ?', 
                        (entry_id, session['user_id'])).fetchone()
    if not entry:
        flash('Entry not found or access denied', 'error')
        return redirect(url_for('gameform', game_id=entry['game_id']))  # Use entry['game_id'] here

    try:
        image_path = os.path.join(app.root_path, 'static', entry['image_path'])
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting image file: {e}")

    db.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
    db.commit()
    flash('Entry deleted successfully!', 'success')

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