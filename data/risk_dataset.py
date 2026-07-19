import pandas as pd

# Sample training data for scam/risk prediction
# Features: crowd_density(1-10), isolation_level(1-10), night_travel(0/1),
#           police_distance_km, past_incidents(count)
# Target: risk_level (0=Safe, 1=Medium, 2=High)

data = {
    'crowd_density': [8, 3, 9, 2, 7, 4, 9, 1, 6, 3, 8, 2, 5, 9, 1, 7, 4, 8, 2, 6],
    'isolation_level': [2, 8, 1, 9, 3, 7, 2, 10, 4, 8, 2, 9, 5, 1, 10, 3, 7, 2, 9, 4],
    'night_travel': [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0],
    'police_distance_km': [1, 15, 0.5, 20, 2, 12, 1, 25, 5, 14, 1, 22, 6, 0.5, 30, 2, 13, 1, 18, 4],
    'past_incidents': [1, 8, 0, 10, 2, 6, 1, 12, 3, 7, 1, 9, 4, 0, 15, 2, 6, 1, 8, 3],
    'risk_level': [0, 2, 0, 2, 0, 1, 0, 2, 1, 2, 0, 2, 1, 0, 2, 0, 1, 0, 2, 1]
}

df = pd.DataFrame(data)

if __name__ == '__main__':
    df.to_csv('risk_data.csv', index=False)
    print("Dataset created successfully!")
    print(df.head())