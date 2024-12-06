# Route Manager Web Application

A modern web-based application for tracking, visualizing, and managing routes. Built with Flask, SQLite, and interactive mapping capabilities.

## Features

- 🗺️ **Interactive Route Mapping**
  - Real-time route visualization
  - Automatic map updates
  - US-centered map view

- 📝 **Route Management**
  - Add routes with start/end addresses
  - Delete individual routes
  - Bulk route import via text file
  - Clear all routes with backup
  - Edit existing routes

- 📊 **Data Analysis**
  - Total distance traveled
  - Average route distance
  - Route history tracking
  - Export routes to CSV

- 🎨 **User Interface**
  - Dark theme by default
  - Responsive design
  - Sortable route table
  - Distance unit conversion (miles/kilometers)

## Technologies Used

- **Backend**
  - Python Flask
  - SQLite database
  - OpenCage Geocoding API
  - GraphHopper Routing API

- **Frontend**
  - HTML5/CSS3
  - JavaScript (jQuery)
  - Bootstrap 5
  - Folium for map generation

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - Unix/MacOS:
     ```bash
     source .venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

## Usage

1. **Adding Routes**
   - Enter start and end addresses
   - Click "Add Route" to save
   - Optional: Add notes for the route

2. **Importing Routes**
   - Create a text file with address pairs
   - Use the "Upload Addresses" feature
   - Each line should contain: start_address|end_address

3. **Managing Routes**
   - Sort routes by clicking column headers
   - Edit routes using the pencil icon
   - Delete routes using the trash icon
   - Export all routes to CSV

4. **Viewing Statistics**
   - Total distance is shown at the top
   - Average route distance is displayed
   - Switch between miles and kilometers

## File Structure

```
web/
├── app.py                  # Main Flask application
├── routes.db               # SQLite database
├── static/
│   ├── cached_map.html     # Cached map 
│   ├── map_last_update.txt # Timestamp of the last cached map
│   ├── script.js           # Frontend JavaScript
│   └── style.css           # Custom styles
├── templates/
│   └── index.html          # Main HTML template
└── uploads/                # Temporary file storage
```

## API Keys

The application uses two external APIs:
- OpenCage Geocoding: For converting addresses to coordinates
- GraphHopper: For route calculations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is open source and available under the MIT License.
