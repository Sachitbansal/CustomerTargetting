"""
Flask API server for the Targeted Calling application with WebSocket support.
"""
import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from database import get_db_connection, init_db, seed_categories

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Paths
BACKEND_DIR = os.path.dirname(__file__)
MOCK_AUDIO_DIR = os.path.join(BACKEND_DIR, 'mock audio')
MOCK_REPORTS_DIR = os.path.join(BACKEND_DIR, 'mock reports')

# Initialize database on startup
init_db()
seed_categories()


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('✅ Client connected')
    emit('connected', {'message': 'Connected to real-time updates'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('❌ Client disconnected')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'API is running'})


# Notification endpoint for NATS consumer
@app.route('/api/notify-update', methods=['POST'])
def notify_update():
    """Receive update notifications from NATS consumer and broadcast via WebSocket"""
    data = request.json
    
    # Broadcast to all connected clients (Flask-SocketIO 5.x compatible)
    socketio.emit('customer_update', data, namespace='/')
    
    return jsonify({'status': 'notified'})


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories."""
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    
    return jsonify([dict(cat) for cat in categories])


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Get reports, optionally filtered by category."""
    category = request.args.get('category')
    
    conn = get_db_connection()
    
    if category:
        reports = conn.execute('''
            SELECT r.*, c.label as category_label, c.prefix as category_prefix
            FROM reports r
            JOIN categories c ON r.category_id = c.id
            WHERE r.category_id = ?
            ORDER BY r.timestamp DESC
        ''', (category,)).fetchall()
    else:
        reports = conn.execute('''
            SELECT r.*, c.label as category_label, c.prefix as category_prefix
            FROM reports r
            JOIN categories c ON r.category_id = c.id
            ORDER BY r.timestamp DESC
        ''').fetchall()
    
    conn.close()
    
    # Get user IDs for each report
    result = []
    for report in reports:
        report_dict = dict(report)
        conn = get_db_connection()
        users = conn.execute('''
            SELECT user_id FROM users WHERE report_id = ?
        ''', (report_dict['id'],)).fetchall()
        conn.close()
        report_dict['userIds'] = [u['user_id'] for u in users]
        result.append(report_dict)
    
    return jsonify(result)


@app.route('/api/reports/<report_id>', methods=['GET'])
def get_report(report_id):
    """Get a single report with all details."""
    conn = get_db_connection()
    
    report = conn.execute('''
        SELECT r.*, c.label as category_label, c.prefix as category_prefix
        FROM reports r
        JOIN categories c ON r.category_id = c.id
        WHERE r.id = ?
    ''', (report_id,)).fetchone()
    
    if not report:
        conn.close()
        return jsonify({'error': 'Report not found'}), 404
    
    users = conn.execute('''
        SELECT * FROM users WHERE report_id = ?
    ''', (report_id,)).fetchall()
    
    conn.close()
    
    report_dict = dict(report)
    report_dict['users'] = [dict(user) for user in users]
    report_dict['userIds'] = [u['user_id'] for u in users]
    
    return jsonify(report_dict)


@app.route('/api/reports/<report_id>/users', methods=['GET'])
def get_report_users(report_id):
    """Get all users for a specific report."""
    conn = get_db_connection()
    
    users = conn.execute('''
        SELECT * FROM users WHERE report_id = ?
    ''', (report_id,)).fetchall()
    
    conn.close()
    
    return jsonify([dict(user) for user in users])


@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get a single user by user_id."""
    conn = get_db_connection()
    
    user = conn.execute('''
        SELECT * FROM users WHERE user_id = ?
    ''', (user_id,)).fetchone()
    
    conn.close()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(dict(user))


# Serve static files (audio and reports)
@app.route('/api/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    """Serve audio files."""
    return send_from_directory(MOCK_AUDIO_DIR, filename)


@app.route('/api/reports/file/<filename>', methods=['GET'])
def serve_report_file(filename):
    """Serve PDF report files."""
    return send_from_directory(MOCK_REPORTS_DIR, filename)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics."""
    conn = get_db_connection()
    
    stats = {
        'totalReports': conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0],
        'totalUsers': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'totalAgreed': conn.execute('SELECT COUNT(*) FROM users WHERE agreed = 1').fetchone()[0],
        'totalDeclined': conn.execute('SELECT COUNT(*) FROM users WHERE agreed = 0').fetchone()[0],
    }
    
    # Category-wise stats
    category_stats = conn.execute('''
        SELECT c.id, c.label, 
               COUNT(DISTINCT r.id) as report_count,
               SUM(r.total_calls) as total_calls,
               SUM(r.successful_calls) as successful_calls
        FROM categories c
        LEFT JOIN reports r ON c.id = r.category_id
        GROUP BY c.id
    ''').fetchall()
    
    conn.close()
    
    stats['categoryStats'] = [dict(cs) for cs in category_stats]
    
    return jsonify(stats)


if __name__ == '__main__':
    print("Starting Flask server with WebSocket support...")
    print("API available at http://localhost:5000")
    print("WebSocket available for real-time updates")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
