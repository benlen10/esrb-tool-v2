import sqlite3
import subprocess
from flask import Flask, render_template, request, jsonify, send_file
import io
import csv

app = Flask(__name__)
DB_PATH = 'esrb_ratings.db'

def init_db():
    """Initialize the SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            game_id INTEGER PRIMARY KEY,
            game_title TEXT NOT NULL,
            platform TEXT,
            rating TEXT,
            descriptors TEXT,
            url TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            games_added INTEGER,
            games_skipped INTEGER
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON ratings(rating)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON ratings(game_title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON ratings(platform)')

    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/ratings')
def get_ratings():
    """API endpoint to get ratings with filtering and pagination"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get query parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    search = request.args.get('search', '')
    platform = request.args.get('platform', '')
    rating = request.args.get('rating', '')
    sort_col = request.args.get('sort', 'game_id')
    sort_dir = request.args.get('dir', 'desc')

    # Whitelist sortable columns
    allowed_sorts = ['game_id', 'game_title', 'platform', 'rating']
    if sort_col not in allowed_sorts:
        sort_col = 'game_id'

    # Build query
    query = 'SELECT * FROM ratings WHERE 1=1'
    params = []

    if search:
        query += ' AND game_title LIKE ?'
        params.append(f'%{search}%')

    if platform:
        query += ' AND platform LIKE ?'
        params.append(f'%{platform}%')

    if rating:
        query += ' AND rating = ?'
        params.append(rating)

    # Get total count
    count_query = query.replace('SELECT *', 'SELECT COUNT(*)')
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Add sorting and pagination
    order_dir = 'DESC' if sort_dir == 'desc' else 'ASC'
    query += f' ORDER BY {sort_col} {order_dir} LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = [dict(row) for row in rows]

    conn.close()

    return jsonify({
        'data': results,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

@app.route('/api/export')
def export_csv():
    """Export filtered data to CSV"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get query parameters
    search = request.args.get('search', '')
    platform = request.args.get('platform', '')
    rating = request.args.get('rating', '')

    # Build query
    query = 'SELECT * FROM ratings WHERE 1=1'
    params = []

    if search:
        query += ' AND game_title LIKE ?'
        params.append(f'%{search}%')

    if platform:
        query += ' AND platform LIKE ?'
        params.append(f'%{platform}%')

    if rating:
        query += ' AND rating = ?'
        params.append(rating)

    query += ' ORDER BY game_title'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['game_id', 'game_title', 'platform', 'rating', 'descriptors', 'url', 'summary'])

    for row in rows:
        writer.writerow([row['game_id'], row['game_title'], row['platform'], row['rating'],
                        row['descriptors'], row['url'], row['summary']])

    conn.close()

    # Convert to bytes for sending
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='esrb_ratings_export.csv'
    )

@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM ratings')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT DISTINCT platform FROM ratings WHERE platform != "" ORDER BY platform')
    platforms = [row[0] for row in cursor.fetchall()]

    cursor.execute('SELECT DISTINCT rating FROM ratings WHERE rating != "" ORDER BY rating')
    ratings = [row[0] for row in cursor.fetchall()]

    cursor.execute('SELECT MAX(scrape_date) FROM scrape_log')
    last_scrape = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'total': total,
        'platforms': platforms,
        'ratings': ratings,
        'last_scrape': last_scrape
    })

@app.route('/api/fetch-new-data', methods=['POST'])
def fetch_new_data():
    """Trigger the scraper to fetch new data"""
    try:
        # Run scrape.py as a subprocess
        result = subprocess.run(['python', 'scrape.py'], capture_output=True, text=True, timeout=600)

        if result.returncode == 0:
            return jsonify({'status': 'success', 'message': 'Data fetch completed successfully'})
        else:
            return jsonify({'status': 'error', 'message': f'Scraper failed: {result.stderr}'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Scraper timed out after 10 minutes'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
