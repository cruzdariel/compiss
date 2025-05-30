import math
import pandas as pd
from flask import Flask, request, jsonify, render_template_string, url_for

# --- Setup ---
app = Flask(__name__, static_folder='static')
# Load bathroom coordinates CSV
# CSV must be in project root with headers like 'Bathroom Name', 'Latitude', 'Longitude'.
df = pd.read_csv('bathrooms.csv')
# Normalize column names
df.rename(columns=lambda x: x.strip().lower().replace(' ', '_'), inplace=True)
# Convert latitude/longitude to numeric and drop invalid rows
for col in ['latitude', 'longitude']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df.dropna(subset=['latitude', 'longitude'], inplace=True)

# --- Geospatial helpers ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    theta = math.degrees(math.atan2(x, y))
    return (theta + 360) % 360

# --- Compute nearest restroom ---
def get_nearest(lat, lon):
    lat, lon = float(lat), float(lon)
    df['distance_km'] = df.apply(lambda r: haversine(lat, lon, r['latitude'], r['longitude']), axis=1)
    df['distance_ft'] = df['distance_km'] * 1000 * 3.28084
    nearest = df.loc[df['distance_ft'].idxmin()]
    return {
        'name': nearest.get('bathroom_name', nearest.get('name', 'Unknown')),
        'distance_ft': nearest['distance_ft'],
        'bearing': bearing(lat, lon, nearest['latitude'], nearest['longitude'])
    }

# --- HTML template -
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Compiss</title>
    <link href="https://fonts.cdnfonts.com/css/comic-sans-ms" rel="stylesheet">
    <link rel="icon" type="image/png" href="static/compass.png">
    <link rel="apple-touch-icon" href="static/icon.png">
    <meta property="og:title" content="Compiss by Polaris">
    <meta property="og:description" content="On campus and need to figure out where to take a piss? Don't miss out on the comPISS, available now. Scav Item 68 (2015)">
    <meta property="og:image" content="https://i.imgur.com/HteHrLb.png">
    <meta property="og:url" content="https://compiss.org">
    <meta name="twitter:card" content="summary_large_image">

    <style>
        body { font-family: 'Comic Sans MS', cursive, sans-serif; padding: 2rem; text-align: center; }
        header { font-size: 2.5rem; margin-bottom: 1rem; }
        #enable-compass, #toggle-compass { margin-bottom: 1rem; }
        .compass-container {
            position: relative; width: 300px; height: 300px;
            margin: 0 auto 1rem; border: 4px solid #333; border-radius: 50%; overflow: hidden;
        }
        #labels-container {
            position: absolute; width: 100%; height: 100%;
            top:0; left:0; transform-origin:50% 50%; transition: transform 0.5s ease;
            pointer-events: none;
        }
        .label { position: absolute; font-size: 1.5rem; font-weight: bold; color:#333; }
        .north { top: 1rem; left: 50%; transform: translateX(-50%); }
        .south { bottom: 1rem; left: 50%; transform: translateX(-50%); }
        .west  { left: 1rem; top: 50%; transform: translateY(-50%); }
        .east  { right: 1rem; top: 50%; transform: translateY(-50%); }
        #compass {
            width: 80%; height: 80%; position: absolute; top:10%; left:10%;
            transform-origin:50% 50%; transition: transform 0.5s ease;
        }
        footer { margin-top: 1.5rem; font-size: 0.9rem; }
    </style>
</head>
<body>
    <header>Compiss</header>
    <button id="enable-compass">Enable Compass Orientation</button>
    <button id="toggle-compass">Toggle Compass Arrow</button>
    <div class="compass-container">
        <div id="labels-container">
            <div class="label north">N</div>
            <div class="label south">S</div>
            <div class="label west">W</div>
            <div class="label east">E</div>
        </div>
        <img id="compass" src="{{ url_for('static', filename='compass.png') }}" alt="Compass">
    </div>
    <p id="info">Waiting for location...</p>
    <script>
        let headingEnabled = false;
        let currentHeading = 0;
        let currentBearing = 0;
        const compass1 = "{{ url_for('static', filename='compass.png') }}";
        const compass2 = "{{ url_for('static', filename='compass2.png') }}";

        function updatePointer() {
            const compass = document.getElementById('compass');
            const rotation = headingEnabled ? currentBearing - currentHeading : currentBearing;
            compass.style.transform = `rotate(${rotation}deg)`;
        }

        function handleOrientation(e) {
            const heading = e.webkitCompassHeading || (e.alpha !== null ? 360 - e.alpha : 0);
            currentHeading = heading;
            document.getElementById('labels-container').style.transform = `rotate(${-heading}deg)`;
            updatePointer();
        }

        const enableBtn = document.getElementById('enable-compass');
        if (window.DeviceOrientationEvent && DeviceOrientationEvent.requestPermission) {
            enableBtn.onclick = () => {
                DeviceOrientationEvent.requestPermission()
                    .then(state => {
                        if (state === 'granted') {
                            headingEnabled = true;
                            window.addEventListener('deviceorientation', handleOrientation, true);
                            enableBtn.style.display = 'none';
                        } else {
                            alert('Compass access denied');
                        }
                    })
                    .catch(console.error);
            };
        } else {
            headingEnabled = true;
            window.addEventListener('deviceorientation', handleOrientation, true);
            enableBtn.style.display = 'none';
        }

        // Toggle compass image
        const toggleBtn = document.getElementById('toggle-compass');
        toggleBtn.addEventListener('click', () => {
            const compassImg = document.getElementById('compass');
            if (compassImg.src.includes('compass.png') && !compassImg.src.includes('compass2.png')) {
                compassImg.src = compass2;
            } else {
                compassImg.src = compass1;
            }
        });

        // Geolocation for nearest restroom
        if (navigator.geolocation) {
            navigator.geolocation.watchPosition(pos => {
                fetch('/update', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat: pos.coords.latitude, lon: pos.coords.longitude })
                })
                .then(res => res.json())
                .then(data => {
                    currentBearing = data.bearing;
                    document.getElementById('info').innerText =
                        `The closest bathroom is ${data.name} (distance: ${data.distance_ft.toFixed(0)} ft)`;
                    updatePointer();
                });
            }, err => console.error(err), { enableHighAccuracy: true, maximumAge: 0, timeout: 5000 });
        } else {
            document.getElementById('info').innerText = 'Geolocation not supported';
        }
    </script>
    <footer><p>Compiss brought to you by <a href="https://dariel.us">Dariel Cruz Rodriguez</a> for Polaris (Campus North)'s <a href="https://scavhunt.uchicago.edu">Scav 2025</a> team!</p><br>
    <strong><p><a href="https://docs.google.com/forms/d/e/1FAIpQLSccbYZvgiRWmq6cPRH_esZXO414OSe3R9UPOKjttVofQTfU-Q/viewform?usp=dialog">Submit your bathroom locations</a></p></strong>
    <strong><p><a href="/map">View current bathroom locations</a></p></strong>
    </footer>
</body>
</html>
'''

# --- Routes ---
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/update', methods=['POST'])
def update():
    payload = request.get_json()
    result = get_nearest(payload['lat'], payload['lon'])
    return jsonify(result)

@app.route('/map')
def show_map():
    markers = df.to_dict(orient='records')
    html_map = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>Compiss - Bathroom Map</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.cdnfonts.com/css/comic-sans-ms" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <style>
            body { font-family: 'Comic Sans MS', cursive, sans-serif; padding: 2rem; text-align: center; }
            header { font-size: 2.5rem; margin-bottom: 1rem; }
            #enable-compass { margin-bottom: 1rem; }
            .compass-container {
                position: relative; width: 300px; height: 300px;
                margin: 0 auto 1rem; border: 4px solid #333; border-radius: 50%; overflow: hidden;
            }
            #labels-container {
                position: absolute; width: 100%; height: 100%;
                top:0; left:0; transform-origin:50% 50%; transition: transform 0.5s ease;
                pointer-events: none;
            }
            .label { position: absolute; font-size: 1.5rem; font-weight: bold; color:#333; }
            .north { top: 1rem; left: 50%; transform: translateX(-50%); }
            .south { bottom: 1rem; left: 50%; transform: translateX(-50%); }
            .west  { left: 1rem; top: 50%; transform: translateY(-50%); }
            .east  { right: 1rem; top: 50%; transform: translateY(-50%); }
            #compass {
                width: 80%; height: 80%; position: absolute; top:10%; left:10%;
                transform-origin:50% 50%; transition: transform 0.5s ease;
            }
            footer { margin-top: 1.5rem; font-size: 0.9rem; }
        </style>
    </head>
    <body>
        <header>Compiss</header>
        <div id="map" style="width: 100%; height: 600px;"></div>
        <script>
            var map = L.map('map').setView([0, 0], 2);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: ''
            }).addTo(map);

            var markers = {{ markers | tojson }};
            var leafletMarkers = [];
            markers.forEach(function(marker) {
                var name = marker.bathroom_name || marker.name || 'Unknown';
                var leafletMarker = L.marker([marker.latitude, marker.longitude])
                                        .bindPopup(name)
                                        .addTo(map);
                leafletMarkers.push(leafletMarker);
            });

            if (leafletMarkers.length > 0) {
                var group = new L.featureGroup(leafletMarkers);
                map.fitBounds(group.getBounds().pad(0.5));
            }
        </script>
        <p><a href="/">Go back</a></p>
    </body>
    </html>
    """
    return render_template_string(html_map, markers=markers)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)