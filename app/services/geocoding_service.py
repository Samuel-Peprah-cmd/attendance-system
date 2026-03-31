import requests

def resolve_location(lat, lng):
    """Converts coordinates to a real address using OpenStreetMap."""
    if not lat or not lng:
        return {'place_name': 'Verified Campus'}
    
    try:
        # Nominatim requires a User-Agent
        headers = {'User-Agent': 'AtomDev_Security_Suite/1.0'}
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}"
        
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            addr = data.get('address', {})
            return {
                'place_name': data.get('display_name', 'Unknown Location'),
                'street': addr.get('road'),
                'town': addr.get('town') or addr.get('suburb') or addr.get('village'),
                'city': addr.get('city'),
                'country': addr.get('country')
            }
    except Exception as e:
        print(f"🌍 Geo-Resolution Error: {e}")
        
    return {'place_name': 'Unknown Location'}