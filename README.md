# Uptime Website Pinger

A simple Flask-based dashboard to monitor the uptime of multiple websites by periodically pinging their URLs. The app provides a real-time web interface with live status updates using WebSockets.

## Features
- Add, remove, and configure URLs to monitor
- Set custom ping intervals per URL (in seconds)
- Real-time status updates and ping history visualization
- Responsive, modern UI (Tailwind CSS)
- Data persistence in JSON files
- Cross-origin support (CORS enabled)

## How It Works
- The backend runs a background thread that pings each configured URL at its specified interval.
- Ping results (success/failure) are stored and visualized in the dashboard.
- The frontend receives live updates via Socket.IO when a ping occurs.

## Requirements
- Python 3.8+
- See `requirements.txt` for dependencies (Flask, Flask-SocketIO, Flask-CORS, requests, python-dotenv)

## Setup
1. **Clone the repository**
2. **Install dependencies**:
   ```sh
   pip install -r requirements.txt
   ```
3. **(Optional) Set a custom port**:
   - Create a `.env` file with `PORT=your_port_number`
   - Or run with `python main.py --port 8080`
4. **Run the app**:
   ```sh
   python main.py
   ```
5. **Open your browser** to [http://localhost:5000](http://localhost:5000) (or your chosen port)

## File Structure
- `main.py` — Main Flask app and ping logic
- `data.json` — List of monitored URLs and intervals
- `ping_history.json` — Recent ping results for each URL
- `static/` — Frontend JS and CSS
- `templates/index.html` — Main dashboard UI
- `requirements.txt` — Python dependencies

## Customization
- Edit `static/style.css` for custom styles
- Modify ping logic or intervals in `main.py`

## License
MIT License
