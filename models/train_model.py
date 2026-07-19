import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import sys
sys.path.append('../data')

# Load the dataset
import os
csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'risk_data.csv')
df = pd.read_csv(csv_path)

# Features and Target
X = df[['crowd_density', 'isolation_level', 'night_travel', 'police_distance_km', 'past_incidents']]
y = df['risk_level']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train the model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Check accuracy
accuracy = model.score(X_test, y_test)
print(f"Model Accuracy: {accuracy * 100:.2f}%")

# Save the model
model_path = os.path.join(os.path.dirname(__file__), 'risk_model.pkl')
joblib.dump(model, model_path)
print("Model saved successfully as risk_model.pkl")