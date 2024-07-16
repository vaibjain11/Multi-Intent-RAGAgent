import requests
import time
import csv
import uuid
import datetime
import os
import json

API_KEY = 'insert your key'
SEARCH_URL = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
DETAILS_URL = 'https://maps.googleapis.com/maps/api/place/details/json'
PLACES_FILENAME = 'nyc_restaurant_place_ids.json'
REVIEWS_FILENAME = 'nyc_restaurant_reviews.csv'
MAX_RESTAURANTS = 15000  # The target number of unique restaurants

def get_saved_place_ids():
    if os.path.isfile(PLACES_FILENAME):
        with open(PLACES_FILENAME, 'r') as file:
            return set(json.load(file))
    else:
        return set()

def save_place_ids(place_ids):
    with open(PLACES_FILENAME, 'w') as file:
        json.dump(list(place_ids), file)

def fetch_restaurant_place_ids(lat, lng, radius=1000, next_page_token=None):
    place_ids = get_saved_place_ids()
    if len(place_ids) >= MAX_RESTAURANTS:
        return set()

    params = {
        'location': f'{lat},{lng}',
        'radius': radius,
        'type': 'restaurant',
        'key': API_KEY
    }
    if next_page_token:
        params['pagetoken'] = next_page_token
        del params['location'], params['radius'], params['type']  # Not needed with pagetoken

    response = requests.get(SEARCH_URL, params=params)
    time.sleep(2)  # Ensuring compliance with Places API query rate
    if response.status_code == 200:
        data = response.json()
        new_place_ids = {place['place_id'] for place in data.get('results', [])}
        save_place_ids(place_ids.union(new_place_ids))
        return new_place_ids, data.get('next_page_token')
    else:
        print("Error:", response.json().get("error_message", "No error message"))
        return set(), None

def fetch_reviews(place_id):
    reviews_data = []
    params = {
        'place_id': place_id,
        'fields': 'reviews,geometry',
        'key': API_KEY
    }
    response = requests.get(DETAILS_URL, params=params)
    if response.status_code == 200:
        result = response.json().get('result', {})
        geometry = result.get('geometry', {}).get('location', {})
        reviews = result.get('reviews', [])
        for review in reviews[:5]:  # Limit to 5 reviews per place
            review_id = str(uuid.uuid4())
            reviews_data.append({
                'review_id': review_id,
                'rating': review.get('rating'),
                'text': review.get('text').replace('\n', ' '),  # Clean newlines from review text
                'time': review.get('time'),
                'restaurant_id': place_id,
                'latitude': geometry.get('lat'),
                'longitude': geometry.get('lng'),
            })
    return reviews_data

def save_to_csv(data, filename):
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        if file.tell() == 0:  # File is empty, write header
            writer.writeheader()
        writer.writerows(data)

def main():
    # New York City bounds for latitudes and longitudes
    nyc_bounds = {
        'lat': [40.680396, 40.882214],
        'lng': [-74.047285, -73.906158]
    }

    # Split the bounds into a grid, this is a simple example with an arbitrary step size
    lat_step = 0.005
    lng_step = 0.005
    radius = 1000  # Search radius in meters

    for lat in (nyc_bounds['lat'][0] + lat_step * i for i in range(int((nyc_bounds['lat'][1] - nyc_bounds['lat'][0]) / lat_step))):
        for lng in (nyc_bounds['lng'][0] + lng_step * j for j in range(int((nyc_bounds['lng'][1] - nyc_bounds['lng'][0]) / lng_step))):
            next_page_token = None
            while True:
                new_place_ids, next_page_token = fetch_restaurant_place_ids(lat, lng, radius, next_page_token)
                for place_id in new_place_ids:
                    reviews_data = fetch_reviews(place_id)
                    if reviews_data:
                        save_to_csv(reviews_data, REVIEWS_FILENAME)
                    time.sleep(1)
                if not next_page_token or len(get_saved_place_ids()) >= MAX_RESTAURANTS:
                    break
                time.sleep(2)  # Must wait before using next_page_token

if __name__ == "__main__":
    if not os.path.exists(REVIEWS_FILENAME):  # Check if the CSV already exists
        with open(REVIEWS_FILENAME, mode='w'):  # Create the CSV file if it does not exist
            pass
    main()
