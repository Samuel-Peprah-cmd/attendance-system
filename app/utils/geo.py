import math
import requests

def calculate_distance(lat1, lon1, lat2, lon2):
    """Returns distance in meters between two points using Haversine formula."""
    if not all([lat1, lon1, lat2, lon2]):
        return 999999 # Treat as outside if data is missing
    
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(dlambda / 2)**2
    
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# def resolve_location(lat, lng):
#     """Converts coordinates to a real address using Nominatim (OSM)."""
#     if not lat or not lng:
#         return {}
    
#     try:
#         # Nominatim requires a User-Agent to identify the app
#         headers = {'User-Agent': 'AtomDev_Security_Suite/1.0'}
#         url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}"
        
#         response = requests.get(url, headers=headers, timeout=3)
#         if response.status_code == 200:
#             data = response.json()
#             addr = data.get('address', {})
            
#             return {
#                 'place_name': data.get('display_name'),
#                 'street': addr.get('road') or addr.get('suburb'),
#                 'town': addr.get('town') or addr.get('village'),
#                 'city': addr.get('city') or addr.get('county'),
#                 'country': addr.get('country')
#             }
#     except Exception as e:
#         print(f"🌍 Geo-Resolution Error: {e}")
        
#     return {'place_name': 'Unknown Location'}