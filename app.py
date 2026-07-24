from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
import requests
import joblib
import os
import textwrap
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'tourguard_secret_key'

# ---------------- Travel Data Import ----------------
import sys
sys.path.append('data')
from travel_data import travel_data

# ---------------- MySQL Connection ----------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "Senthooran@123"),
        database=os.environ.get("DB_NAME", "tourguard_ai"),
        port=int(os.environ.get("DB_PORT", 3306))
    )

def save_search_history(username, location, travel_date, risk):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO search_history (username, location, travel_date, risk_level) VALUES (%s, %s, %s, %s)",
        (username, location, travel_date, risk)
    )
    conn.commit()
    cursor.close()
    conn.close()

# ---------------- Weather ----------------
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "3aa5ab69ed8a2c569081f1b5ab327c5e")

def get_weather(location):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            "temperature": data['main']['temp'],
            "description": data['weather'][0]['description'],
            "humidity": data['main']['humidity']
        }
    else:
        return None

# ---------------- AI Risk Model ----------------
model_path = os.path.join(os.path.dirname(__file__), 'models', 'risk_model.pkl')
risk_model = joblib.load(model_path)

LOCATION_FACTORS = {
    "Munnar":     {"crowd_density": 7, "isolation_level": 4, "night_travel": 0, "police_distance_km": 3, "past_incidents": 2},
    "Ooty":       {"crowd_density": 8, "isolation_level": 3, "night_travel": 0, "police_distance_km": 2, "past_incidents": 1},
    "Kodaikanal": {"crowd_density": 6, "isolation_level": 6, "night_travel": 0, "police_distance_km": 5, "past_incidents": 3},
    "Coorg":      {"crowd_density": 5, "isolation_level": 7, "night_travel": 0, "police_distance_km": 8, "past_incidents": 4},
    "Goa":        {"crowd_density": 9, "isolation_level": 2, "night_travel": 1, "police_distance_km": 1, "past_incidents": 5},
}

def get_location_factors(location):
    return LOCATION_FACTORS.get(location, {"crowd_density": 5, "isolation_level": 5, "night_travel": 0, "police_distance_km": 5, "past_incidents": 3})

def predict_risk(location):
    factors = get_location_factors(location)

    features = [[
        factors["crowd_density"],
        factors["isolation_level"],
        factors["night_travel"],
        factors["police_distance_km"],
        factors["past_incidents"]
    ]]

    prediction = risk_model.predict(features)[0]

    risk_labels = {0: "Safe ✅", 1: "Medium Risk ⚠️", 2: "High Risk 🚨"}
    return risk_labels.get(prediction, "Unknown")

def generate_risk_reason(location, risk, weather, info):
    factors = get_location_factors(location)
    reasons = []

    if factors["crowd_density"] >= 7:
        reasons.append("This destination has high tourist footfall, which generally means more people around and quicker access to help if needed.")
    else:
        reasons.append("Some stretches here see fewer tourists, so travelling in a group is recommended.")

    if factors["isolation_level"] >= 6:
        reasons.append("Certain areas near this location are relatively isolated, which increases risk if something goes wrong far from town.")
    else:
        reasons.append("Most tourist areas here are well-connected and not heavily isolated.")

    if factors["night_travel"] == 1:
        reasons.append("Night travel is more common in this region, which statistically increases risk due to lower visibility on roads.")
    else:
        reasons.append("Night travel is minimal in this region, which helps keep the overall risk lower.")

    if factors["police_distance_km"] <= 3:
        reasons.append(f"The nearest police station is only about {factors['police_distance_km']} km away, enabling a quick emergency response.")
    else:
        reasons.append(f"The nearest police station is around {factors['police_distance_km']} km away, so save emergency contacts in advance.")

    if factors["past_incidents"] <= 2:
        reasons.append("Very few safety incidents have been recorded in this area historically.")
    else:
        reasons.append(f"Around {factors['past_incidents']} past incidents have been recorded here, which the AI model factored into this prediction.")

    danger_zone_count = len(info.get('danger_zones', []))
    if danger_zone_count > 0:
        reasons.append(f"The system has flagged {danger_zone_count} known danger zone(s) in this area - check the Danger Zones section before you travel.")
    else:
        reasons.append("No specific danger zones are currently flagged for this destination.")

    if weather:
        desc = weather.get('description', '').lower()
        if 'rain' in desc or 'storm' in desc or 'thunder' in desc:
            reasons.append(f"Current weather shows '{weather.get('description')}', which can affect road conditions - drive with extra caution.")
        elif weather.get('humidity', 0) >= 80:
            reasons.append(f"Humidity is high at {weather.get('humidity')}%, which may cause foggy or slippery conditions in hilly areas.")
        else:
            reasons.append(f"Current weather ('{weather.get('description')}') looks favourable for travel.")

    if "Safe" in risk:
        reasons.append("Overall, the combined factors place this trip in the SAFE category - standard travel precautions are sufficient.")
    elif "Medium" in risk:
        reasons.append("Overall, this trip falls under MEDIUM risk - stay alert, especially in isolated or poorly lit areas.")
    else:
        reasons.append("Overall, this trip falls under HIGH risk - extra precautions, group travel, and daytime-only movement are strongly advised.")

    reasons.append("This prediction was generated by a Random Forest model trained on crowd density, isolation level, night travel patterns, police proximity, and historical incident data.")

    return reasons

# ---------------- Trip Cost Calculator ----------------
def calculate_trip_cost(vehicle, distance_km, num_days, location, hotel_tier):
    distance_km = float(distance_km)
    num_days = int(num_days)

    PETROL_PRICE = 105

    if vehicle == "Bike":
        mileage = 40
    else:
        mileage = 15

    fuel_needed = distance_km / mileage
    fuel_cost = fuel_needed * PETROL_PRICE

    hotel_rates = travel_data.get(location, {}).get('avg_hotel_cost_per_night', {"3_star": 2000, "5_star": 6000})
    hotel_per_night = hotel_rates.get(hotel_tier, 2000)
    hotel_cost = hotel_per_night * num_days

    food_cost_per_day = 600
    food_cost = food_cost_per_day * num_days

    total_cost = fuel_cost + hotel_cost + food_cost

    return {
        "fuel_cost": round(fuel_cost, 2),
        "hotel_cost": round(hotel_cost, 2),
        "hotel_per_night": hotel_per_night,
        "food_cost": round(food_cost, 2),
        "total_cost": round(total_cost, 2),
        "fuel_needed_litres": round(fuel_needed, 2)
    }

# ---------------- PDF Report Generator ----------------
class WatermarkPDF(FPDF):
    def header(self):
        # Automatic diagonal watermark on every page
        self.set_font("Arial", 'B', 55)
        self.set_text_color(232, 232, 232)
        with self.rotation(45, x=105, y=160):
            self.text(35, 170, "SENTHOORAN")
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"TourGuard_AI Report  |  Page {self.page_no()}  |  Developed by Senthooran M", align='C')


def section_box(pdf, title, items):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", 'B', 12.5)
    pdf.set_fill_color(23, 35, 47)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, txt=f"  {title}", border=0, fill=True, ln=True)
    pdf.set_font("Arial", size=10.5)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(245, 247, 249)
    for item in items:
        clean_item = item.encode('latin-1', 'ignore').decode('latin-1')
        wrapped_lines = textwrap.wrap(clean_item, width=95)
        if not wrapped_lines:
            wrapped_lines = [""]
        first_line = True
        for line in wrapped_lines:
            prefix = "   -  " if first_line else "      "
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 7.5, txt=f"{prefix}{line}", border=0, fill=True, ln=True)
            first_line = False
    pdf.ln(4)


def generate_pdf_report(location, travel_date, info, weather, risk):
    pdf = WatermarkPDF()
    pdf.add_page()

    # ---------- Header Banner ----------
    pdf.set_fill_color(23, 35, 47)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_xy(0, 8)
    pdf.set_font("Arial", 'B', 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(210, 10, txt="TourGuard_AI - Travel Safety Report", align='C', ln=True)
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(180, 210, 235)
    pdf.set_x(0)
    pdf.cell(210, 8, txt=f"{location}   |   Travel Date: {travel_date}", align='C', ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(38)

    # ---------- Risk + Weather Row ----------
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(23, 35, 47)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(95, 9, txt="AI Risk Prediction", border=0, fill=True, align='C')
    pdf.cell(95, 9, txt="Weather Conditions", border=0, fill=True, align='C', ln=True)

    pdf.set_font("Arial", size=11)
    pdf.set_fill_color(245, 247, 249)
    pdf.set_text_color(20, 20, 20)
    risk_clean = risk.encode('latin-1', 'ignore').decode('latin-1')
    weather_text = f"{weather['temperature']}C, {weather['description']}, {weather['humidity']}% humidity" if weather else "N/A"
    weather_clean = weather_text.encode('latin-1', 'ignore').decode('latin-1')
    pdf.cell(95, 10, txt=risk_clean, border=0, fill=True, align='C')
    pdf.cell(95, 10, txt=weather_clean, border=0, fill=True, align='C', ln=True)
    pdf.ln(8)

    # ---------- Content Sections ----------
    section_box(pdf, "Tourist Spots", info.get('tourist_spots', []))
    section_box(pdf, "Danger Zones", info.get('danger_zones', []))
    section_box(pdf, "Police Stations", info.get('police_stations', []))
    section_box(pdf, "Petrol Bunks", info.get('petrol_bunks', []))
    section_box(pdf, "Travel Tips", info.get('travel_tips', []))

    # ---------- Hotels Table ----------
    pdf.set_font("Arial", 'B', 12.5)
    pdf.set_fill_color(23, 35, 47)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, txt="  Hotel Recommendations", border=0, fill=True, ln=True)

    pdf.set_font("Arial", 'B', 9.5)
    pdf.set_fill_color(225, 230, 235)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(65, 8, txt="Hotel Name", border=1, fill=True, align='C')
    pdf.cell(22, 8, txt="Rating", border=1, fill=True, align='C')
    pdf.cell(32, 8, txt="Price/Night", border=1, fill=True, align='C')
    pdf.cell(71, 8, txt="Review", border=1, fill=True, align='C', ln=True)

    pdf.set_font("Arial", size=9)
    for h in info.get('hotels', []):
        name_clean = h['name'].encode('latin-1', 'ignore').decode('latin-1')
        stars = str(h.get('stars', 0)) + " star"
        price = f"Rs.{h['price_per_night']}"
        review_clean = h.get('review', '')[:50].encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(65, 8, txt=name_clean, border=1)
        pdf.cell(22, 8, txt=stars, border=1, align='C')
        pdf.cell(32, 8, txt=price, border=1, align='C')
        pdf.cell(71, 8, txt=review_clean, border=1, ln=True)

    pdf_path = os.path.join(os.path.dirname(__file__), 'static', 'travel_report.pdf')
    pdf.output(pdf_path)
    return pdf_path

# ---------------- ROUTES ----------------
@app.route('/about-app')
def about_app():
    return render_template('about.html',
        page_title="About TourGuard_AI",
        heading="About the App",
        content=[
            "TourGuard_AI is a real-time, AI-powered travel safety companion built to help travellers make safer, smarter decisions before and during their trip.",
            "It combines a machine learning risk prediction model, live weather data, curated tourist information, smart itinerary planning, and budget estimation into a single, easy-to-use platform.",
            "From login to a complete downloadable report, every step is designed to be fast, secure, and genuinely useful for real-world travel planning."
        ]
    )

@app.route('/about-developer')
def about_developer():
    return render_template('about.html',
        page_title="About Developer",
        heading="Senthooran M",
        content=[
            "Senthooran M is a third-year BCA Data Analytics student at Sri Krishna Adithya College of Arts and Science, Coimbatore, and also serves as the Placement Coordinator for his department.",
            "He completed a specialized Data Analytics course at IIE, where TourGuard_AI was conceived and built as part of Project Spark - a platform to design real-world, startup-quality tech solutions.",
            "TourGuard_AI reflects his interest in combining data analytics, machine learning, and thoughtful UI design to build products that solve genuine, everyday problems - in this case, making travel safer and smarter for everyone."
        ]
    )
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        session['username'] = username
        return render_template('dashboard.html', username=username)
    else:
        return "Invalid Username or Password! <a href='/'>Try Again</a>"

@app.route('/dashboard')
def dashboard():
    username = session.get('username', 'Guest')
    return render_template('dashboard.html', username=username)

@app.route('/analyze', methods=['POST'])
def analyze():
    location = request.form['location']
    travel_date = request.form['travel_date']
    vehicle = request.form['vehicle']
    distance_km = request.form['distance_km']
    num_days = request.form['num_days']
    hotel_tier = request.form['hotel_tier']

    info = travel_data.get(location, {})
    weather = get_weather(location)
    risk = predict_risk(location)
    risk_reason = generate_risk_reason(location, risk, weather, info)
    trip_cost = calculate_trip_cost(vehicle, distance_km, num_days, location, hotel_tier)

    username = session.get('username', 'Guest')
    save_search_history(username, location, travel_date, risk)

    return render_template('report.html',
                           location=location,
                           travel_date=travel_date,
                           vehicle=vehicle,
                           distance_km=distance_km,
                           num_days=num_days,
                           hotel_tier=hotel_tier,
                           info=info,
                           weather=weather,
                           risk=risk,
                           risk_reason=risk_reason,
                           trip_cost=trip_cost)

@app.route('/download_report', methods=['POST'])
def download_report():
    location = request.form['location']
    travel_date = request.form['travel_date']

    info = travel_data.get(location, {})
    weather = get_weather(location)
    risk = predict_risk(location)

    pdf_path = generate_pdf_report(location, travel_date, info, weather, risk)
    return send_file(pdf_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
