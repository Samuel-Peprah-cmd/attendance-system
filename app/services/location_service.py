import requests
from flask import current_app

def reverse_geocode_google(lat, lng):
    """
    Production-grade GPS resolution using Google Maps Platform.
    Requires GOOGLE_MAPS_API_KEY in your .env
    """
    api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {'place_name': 'GPS Locked (Internal)'}

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key,
        "language": "en"
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data.get("status") == "OK":
            result = data["results"][0]
            components = result.get("address_components", [])
            
            # Extract specific details
            addr_data = {
                'place_name': result.get("formatted_address"),
                'street': next((c['long_name'] for c in components if 'route' in c['types']), None),
                'town': next((c['long_name'] for c in components if 'sublocality' in c['types']), None),
                'city': next((c['long_name'] for c in components if 'locality' in c['types']), None),
                'country': next((c['long_name'] for c in components if 'country' in c['types']), 'Ghana'),
                'lat': lat,
                'lng': lng,
                'map_url': f"https://www.google.com/maps?q={lat},{lng}"
            }
            return addr_data
    except Exception as e:
        print(f"🌍 Google Geo Error: {e}")
    
    return {'place_name': 'Campus Entry'}