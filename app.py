from flask import Flask, render_template, request, jsonify, send_file, Response, g, after_this_request
import sqlite3
import requests
import json
import folium
import os
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil
import csv
from functools import wraps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

import credentials
OPENCAGE_API_KEY = credentials.OPENCAGE_API_KEY
GRAPHHOPPER_API_KEY = credentials.GRAPHHOPPER_API_KEY


def init_db():
    conn = sqlite3.connect('routes.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS routes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  start_address TEXT NOT NULL,
                  end_address TEXT NOT NULL,
                  distance REAL,
                  date TEXT,
                  notes TEXT,
                  route_points TEXT)''')
    conn.commit()
    conn.close()

def backup_database():
    backup_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'routes_backup_{timestamp}.db')
    shutil.copy2('routes.db', backup_path)
    return backup_path

def restore_database(backup_file):
    try:
        shutil.copy2(backup_file, 'routes.db')
        return True
    except Exception as e:
        print(f"Restore error: {e}")
        return False

def export_to_csv():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get all routes but exclude route_points column
        routes = cursor.execute("SELECT id, start_address, end_address, distance, date, notes FROM routes ORDER BY date DESC").fetchall()
        
        # Create a temporary file in system temp directory
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', newline='', encoding='utf-8')
        
        # Write to CSV
        writer = csv.writer(temp_file)
        writer.writerow(['ID', 'Start Address', 'End Address', 'Distance (km)', 'Date', 'Notes'])  # Headers
        writer.writerows(routes)
        
        temp_file.close()
        return temp_file.name
        
    except Exception as e:
        print(f"Error in export_to_csv: {e}")
        if 'temp_file' in locals():
            temp_file.close()
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise
    finally:
        conn.close()

def geocode_address(address):
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_API_KEY}"
        response = requests.get(url)
        data = response.json()
        if data['results']:
            location = data['results'][0]['geometry']
            return [location['lat'], location['lng']]
        return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def calculate_route(start_coords, end_coords):
    try:
        url = f"https://graphhopper.com/api/1/route?point={start_coords[0]},{start_coords[1]}&point={end_coords[0]},{end_coords[1]}&vehicle=car&points_encoded=false&key={GRAPHHOPPER_API_KEY}"
        response = requests.get(url)
        data = response.json()
        if 'paths' in data and data['paths']:
            path = data['paths'][0]
            return {
                'distance': path['distance'] / 1000,  # Convert to kilometers
                'points': path['points']['coordinates']  # List of [lon, lat] coordinates
            }
        return None
    except Exception as e:
        print(f"Route calculation error: {e}")
        return None

def get_last_update_time():
    try:
        conn = sqlite3.connect('routes.db')
        c = conn.cursor()
        result = c.execute('SELECT MAX(date) as last_update FROM routes').fetchone()
        conn.close()
        return result['last_update'] if result['last_update'] else None
    except:
        return None

def should_regenerate_map():
    cache_file = os.path.join(os.path.dirname(__file__), 'static', 'map_last_update.txt')
    routes_file = os.path.join(os.path.dirname(__file__), 'routes.db')
    
    # If no cache file exists, regenerate
    if not os.path.exists(cache_file):
        return True
    
    # Read last map update time
    with open(cache_file, 'r') as f:
        try:
            last_map_update = datetime.fromisoformat(f.read().strip())
        except (ValueError, FileNotFoundError):
            return True
    
    # Get routes database modification time
    routes_mod_time = datetime.fromtimestamp(os.path.getmtime(routes_file))
    
    # Regenerate if routes have been modified since last map update
    return routes_mod_time > last_map_update

def get_db():
    conn = sqlite3.connect('routes.db')
    conn.row_factory = sqlite3.Row
    return conn

def after_this_request(func):
    if not hasattr(g, 'call_after_request'):
        g.call_after_request = []
    g.call_after_request.append(func)
    return func

@app.after_request
def per_request_callbacks(response):
    for func in getattr(g, 'call_after_request', ()):
        response = func(response)
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_route', methods=['POST'])
def add_route():
    data = request.get_json()
    start_address = data.get('start_address')
    end_address = data.get('end_address')
    notes = data.get('notes', '')
    
    start_coords = geocode_address(start_address)
    end_coords = geocode_address(end_address)
    
    if start_coords and end_coords:
        route_data = calculate_route(start_coords, end_coords)
        if route_data:
            conn = get_db()
            conn.execute("""INSERT INTO routes 
                        (start_address, end_address, distance, date, notes, route_points) 
                        VALUES (?, ?, ?, date('now'), ?, ?)""",
                     (start_address, end_address, route_data['distance'], notes, 
                      json.dumps(route_data['points'])))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'distance': route_data['distance']})
    
    return jsonify({'success': False, 'error': 'Could not calculate route'})

@app.route('/get_routes')
def get_routes():
    conn = get_db()
    routes = conn.execute("SELECT * FROM routes ORDER BY date DESC").fetchall()
    conn.close()
    return jsonify([{
        'id': route['id'], 
        'start': route['start_address'], 
        'end': route['end_address'], 
        'distance': route['distance'], 
        'date': route['date'], 
        'notes': route['notes'] or ''
    } for route in routes])

@app.route('/delete_route/<int:route_id>', methods=['DELETE'])
def delete_route(route_id):
    try:
        db = get_db()
        db.execute('DELETE FROM routes WHERE id = ?', (route_id,))
        db.commit()
        return jsonify({'success': True, 'route_id': route_id})
    except Exception as e:
        print(f"Error deleting route: {str(e)}")
        return jsonify({'success': False, 'error': str(e), 'route_id': route_id}), 500

@app.route('/update_route/<int:route_id>', methods=['PUT'])
def update_route(route_id):
    data = request.get_json()
    start_address = data.get('start_address')
    end_address = data.get('end_address')
    notes = data.get('notes', '')
    
    start_coords = geocode_address(start_address)
    end_coords = geocode_address(end_address)
    
    if start_coords and end_coords:
        route_data = calculate_route(start_coords, end_coords)
        if route_data:
            conn = get_db()
            conn.execute("""UPDATE routes 
                        SET start_address = ?, 
                            end_address = ?, 
                            distance = ?,
                            notes = ?,
                            route_points = ?
                        WHERE id = ?""", 
                     (start_address, end_address, route_data['distance'], notes,
                      json.dumps(route_data['points']), route_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Could not calculate new route'})

@app.route('/backup_database', methods=['POST'])
def backup_db():
    backup_path = backup_database()
    return jsonify({'success': True, 'backup_path': backup_path})

@app.route('/restore_database', methods=['POST'])
def restore_db():
    if 'backup_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})
    
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    backup_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_backup.db')
    file.save(backup_path)
    
    if restore_database(backup_path):
        os.remove(backup_path)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Restore failed'})

@app.route('/export_csv')
def export_csv():
    try:
        temp_file_path = export_to_csv()
        
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_file_path)
                print(f"Successfully deleted temporary file: {temp_file_path}")
            except Exception as e:
                print(f"Error cleaning up temporary file: {e}")
            return response
        
        return send_file(
            temp_file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'routes_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({'error': 'Failed to export CSV'}), 500

@app.route('/clear_database', methods=['POST'])
def clear_db():
    backup_database()  # Create backup before clearing
    conn = get_db()
    conn.execute("DELETE FROM routes")
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/get_map')
def get_map():
    try:
        # Connect to database and fetch routes
        conn = get_db()
        routes = conn.execute("SELECT * FROM routes ORDER BY date DESC").fetchall()
        conn.close()
        
        # If no routes, return empty map
        if not routes:
            return jsonify({'html': '<div class="text-center">No routes to display</div>'})
        
        # Create map with all routes
        # Use a default center that makes sense (e.g., US center)
        m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
        
        # Add route points to map
        for route in routes:
            try:
                # Ensure route_points is parsed correctly
                route_points = json.loads(route['route_points']) if route['route_points'] else []
                
                if route_points:
                    # Swap latitude and longitude to ensure correct order (lon, lat)
                    corrected_route_points = [[point[1], point[0]] for point in route_points]
                    
                    # Add markers and route line
                    start_coords = corrected_route_points[0]
                    end_coords = corrected_route_points[-1]
                    
                    folium.Marker(
                        location=start_coords, 
                        popup=f"Start: {route['start_address']}",
                        icon=folium.Icon(color='green', icon='play')
                    ).add_to(m)
                    
                    folium.Marker(
                        location=end_coords, 
                        popup=f"End: {route['end_address']}",
                        icon=folium.Icon(color='red', icon='stop')
                    ).add_to(m)
                    
                    # Draw route line
                    folium.PolyLine(
                        locations=corrected_route_points, 
                        color='blue', 
                        weight=2, 
                        opacity=0.8
                    ).add_to(m)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Error processing route points for route: {route['id']} - {str(e)}")
        
        # Generate map HTML
        map_html = m._repr_html_()
        
        # Save map to cached HTML (optional, but can improve performance)
        cached_map_path = os.path.join(os.path.dirname(__file__), 'static', 'cached_map.html')
        with open(cached_map_path, 'w', encoding='utf-8') as f:
            f.write(map_html)
        
        # Update last update time
        with open(os.path.join(os.path.dirname(__file__), 'static', 'map_last_update.txt'), 'w') as f:
            f.write(datetime.now().isoformat())
        
        return jsonify({'html': map_html, 'regenerated': True})
    
    except Exception as e:
        print(f"Error generating map: {str(e)}")
        return jsonify({'error': 'Failed to generate map', 'details': str(e)})

@app.route('/get_statistics')
def get_statistics():
    conn = get_db()
    
    # Total routes
    total_routes = conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
    
    # Total distance
    total_distance = conn.execute("SELECT SUM(distance) FROM routes").fetchone()[0] or 0
    
    # Average distance
    avg_distance = conn.execute("SELECT AVG(distance) FROM routes").fetchone()[0] or 0
    
    # Routes per day
    daily_routes = dict(conn.execute("SELECT date, COUNT(*) FROM routes GROUP BY date ORDER BY date DESC").fetchall())
    
    conn.close()
    
    return jsonify({
        'total_routes': total_routes,
        'total_distance': round(total_distance, 2),
        'average_distance': round(avg_distance, 2),
        'daily_routes': daily_routes
    })

@app.route('/upload_addresses', methods=['POST'])
def upload_addresses():
    print("=== Starting address upload processing ===")
    
    try:
        if 'file' not in request.files:
            print("Error: No file part in request")
            return jsonify({'type': 'error', 'error': 'No file uploaded'})
        
        file = request.files['file']
        start_address = request.form.get('startAddress')
        
        print(f"Received file: {file.filename}")
        print(f"Start address: {start_address}")
        
        if not file or not file.filename:
            print("Error: No file selected")
            return jsonify({'type': 'error', 'error': 'No file selected'})
            
        if not start_address:
            print("Error: No start address provided")
            return jsonify({'type': 'error', 'error': 'Start address is required'})

        # Create a temporary file to store the uploaded content
        temp_file_path = os.path.join(os.path.dirname(__file__), 'temp_addresses.txt')
        file.save(temp_file_path)

        def generate():
            try:
                # Read addresses from saved file
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    addresses = [line.strip() for line in f if line.strip()]
                
                # Clean up temp file
                try:
                    os.remove(temp_file_path)
                except:
                    pass
                
                total = len(addresses)
                print(f"Total addresses to process: {total}")
                
                successful = 0
                
                # Process start address first
                try:
                    print(f"Geocoding start address: {start_address}")
                    start_coords = geocode_address(start_address)
                    if not start_coords:
                        print(f"Error geocoding start address: {start_address}")
                        yield json.dumps({
                            'type': 'error',
                            'error': f'Could not geocode start address: {start_address}'
                        }) + '\n'
                        return
                    print(f"Start address geocoded successfully: {start_coords}")
                except Exception as e:
                    print(f"Exception geocoding start address: {str(e)}")
                    yield json.dumps({
                        'type': 'error',
                        'error': f'Error processing start address: {str(e)}'
                    }) + '\n'
                    return

                # Process each destination address
                for i, address in enumerate(addresses, 1):
                    try:
                        print(f"Processing address {i}/{total}: {address}")
                        
                        # Geocode the destination address
                        coords = geocode_address(address)
                        if not coords:
                            print(f"Failed to geocode address: {address}")
                            yield json.dumps({
                                'type': 'progress',
                                'progress': (i * 100) // total,
                                'current': i,
                                'total': total,
                                'address': address,
                                'success': False,
                                'error': 'Could not geocode address'
                            }) + '\n'
                            continue

                        print(f"Successfully geocoded address: {address} -> {coords}")
                        
                        # Calculate route
                        route_data = calculate_route(start_coords, coords)
                        if not route_data:
                            print(f"Failed to calculate route for: {address}")
                            yield json.dumps({
                                'type': 'progress',
                                'progress': (i * 100) // total,
                                'current': i,
                                'total': total,
                                'address': address,
                                'success': False,
                                'error': 'Could not calculate route'
                            }) + '\n'
                            continue

                        print(f"Successfully calculated route for: {address}")
                        
                        # Save to database
                        route_points = route_data.get('points', [])
                        distance = route_data.get('distance', 0)
                        
                        db = get_db()
                        db.execute(
                            'INSERT INTO routes (start_address, end_address, distance, date, route_points) VALUES (?, ?, ?, ?, ?)',
                            (start_address, address, distance, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), json.dumps(route_points))
                        )
                        db.commit()
                        db.close()
                        
                        successful += 1
                        print(f"Successfully saved route to database for: {address}")
                        
                        yield json.dumps({
                            'type': 'progress',
                            'progress': (i * 100) // total,
                            'current': i,
                            'total': total,
                            'address': address,
                            'success': True
                        }) + '\n'
                        
                    except Exception as e:
                        print(f"Error processing address {address}: {str(e)}")
                        yield json.dumps({
                            'type': 'progress',
                            'progress': (i * 100) // total,
                            'current': i,
                            'total': total,
                            'address': address,
                            'success': False,
                            'error': str(e)
                        }) + '\n'

                print(f"Processing complete. {successful} successful out of {total}")
                yield json.dumps({
                    'type': 'complete',
                    'successful': successful,
                    'total': total
                }) + '\n'
                
            except Exception as e:
                print(f"Fatal error during processing: {str(e)}")
                yield json.dumps({
                    'type': 'error',
                    'error': f'Error processing file: {str(e)}'
                }) + '\n'
                
                # Clean up temp file in case of error
                try:
                    os.remove(temp_file_path)
                except:
                    pass

        return Response(generate(), mimetype='application/x-json-stream')
        
    except Exception as e:
        print(f"Unexpected error in upload_addresses: {str(e)}")
        return jsonify({'type': 'error', 'error': f'Unexpected error: {str(e)}'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)