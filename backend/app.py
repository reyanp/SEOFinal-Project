import os
from typing import Optional, Tuple, List, Dict, Any

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv


# Load environment variables from backend/.env explicitly (not project root)
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

app = Flask(__name__)
CORS(app)  # allow requests from the frontend dev server

API_KEY = os.getenv("Maps_API_KEY")

@app.get("/")
def root() -> Any:
    return (
        """
        <html>
          <body style="font-family:system-ui; padding:20px;">
            <h2>Let's Meet API</h2>
            <p>This server only provides API endpoints.</p>
            <ul>
              <li>Health check: <a href="/api/health">/api/health</a></li>
              <li>Open the app UI at: <code>http://localhost:5500</code></li>
            </ul>
          </body>
        </html>
        """,
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


def get_coordinates_by_address(address: str) -> Tuple[Optional[float], Optional[float]]:
    """Geocode a free‑text address to (lat, lng) using Google Geocoding API."""
    if not API_KEY:
        return None, None

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        resp = requests.get(url, params={"address": address, "key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None, None

        location = data["results"][0]["geometry"]["location"]
        return float(location["lat"]), float(location["lng"])
    except Exception:
        return None, None


def get_coordinates_by_place_id(place_id: str) -> Tuple[Optional[float], Optional[float]]:
    """Geocode a Google place_id to (lat, lng) using Geocoding API."""
    if not API_KEY:
        return None, None
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        resp = requests.get(url, params={"place_id": place_id, "key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None, None
        location = data["results"][0]["geometry"]["location"]
        return float(location["lat"]), float(location["lng"])
    except Exception:
        return None, None


def search_places_nearby(latitude: float, longitude: float, place_type: str, radius_meters: int = 3000) -> List[Dict[str, Any]]:
    """Search nearby places by type near a location using Places Nearby Search API."""
    if not API_KEY:
        return []

    try:
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius_meters,
            "type": place_type,  # expects a valid Places type like 'restaurant', 'cafe', etc.
            "key": API_KEY,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])

        # Keep only fields we actually need on the frontend (beginner-friendly)
        simplified: List[Dict[str, Any]] = []
        for r in results:
            location = r.get("geometry", {}).get("location", {})
            simplified.append(
                {
                    "name": r.get("name"),
                    "rating": r.get("rating"),
                    "user_ratings_total": r.get("user_ratings_total"),
                    "address": r.get("vicinity") or r.get("formatted_address"),
                    "place_id": r.get("place_id"),
                    "location": {"lat": location.get("lat"), "lng": location.get("lng")},
                    "maps_url": f"https://www.google.com/maps/search/?api=1&query_place_id={r.get('place_id')}",
                }
            )
        return simplified
    except Exception:
        return []


def add_driving_times(
    places: List[Dict[str, Any]],
    origin1: Dict[str, float],
    origin2: Dict[str, float],
) -> None:
    """Annotate each place with driving time from origin1 and origin2 using Distance Matrix API."""
    if not API_KEY or not places:
        return

    # Limit destinations to avoid hitting matrix element caps (2 origins * N dest <= 100)
    max_destinations = 20
    destinations = places[:max_destinations]
    dest_param = "|".join(
        f"{p['location']['lat']},{p['location']['lng']}" for p in destinations if p.get("location") and p['location'].get('lat') and p['location'].get('lng')
    )
    if not dest_param:
        return

    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{origin1['lat']},{origin1['lng']}|{origin2['lat']},{origin2['lng']}",
            "destinations": dest_param,
            "mode": "driving",
            "units": "imperial",
            "key": API_KEY,
            "avoid": "",  # Don't avoid anything to maximize success
        }
        resp = requests.get(url, params=params, timeout=30)  # Longer timeout for distant locations
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "OK":
            # If driving fails, try transit as fallback
            add_fallback_times(destinations, origin1, origin2)
            return
            
        rows = data.get("rows", [])
        if len(rows) < 2:
            add_fallback_times(destinations, origin1, origin2)
            return
            
        row1, row2 = rows[0], rows[1]
        elems1 = row1.get("elements", [])
        elems2 = row2.get("elements", [])
        
        for idx, place in enumerate(destinations):
            # Guard index and element status
            d1 = elems1[idx] if idx < len(elems1) else {}
            d2 = elems2[idx] if idx < len(elems2) else {}
            
            if d1.get("status") == "OK":
                place["travel_time_from_origin1_text"] = d1.get("duration", {}).get("text")
                place["travel_distance_from_origin1_text"] = d1.get("distance", {}).get("text")
            else:
                # Fallback: calculate straight-line distance and estimate time
                add_estimated_time(place, origin1, "origin1")
                
            if d2.get("status") == "OK":
                place["travel_time_from_origin2_text"] = d2.get("duration", {}).get("text")
                place["travel_distance_from_origin2_text"] = d2.get("distance", {}).get("text")
            else:
                # Fallback: calculate straight-line distance and estimate time
                add_estimated_time(place, origin2, "origin2")
                
    except Exception:
        # Complete fallback: estimate times for all places
        add_fallback_times(destinations, origin1, origin2)
        return


def add_estimated_time(place: Dict[str, Any], origin: Dict[str, float], origin_key: str) -> None:
    """Add estimated travel time based on straight-line distance."""
    try:
        place_lat = place["location"]["lat"]
        place_lng = place["location"]["lng"]
        origin_lat = origin["lat"]
        origin_lng = origin["lng"]
        
        # Calculate straight-line distance using Haversine formula
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959  # Earth radius in miles
        lat1, lng1 = radians(origin_lat), radians(origin_lng)
        lat2, lng2 = radians(place_lat), radians(place_lng)
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_miles = R * c
        
        # Estimate driving time (assume 35 mph average with traffic)
        estimated_hours = distance_miles / 35
        estimated_minutes = int(estimated_hours * 60)
        
        if estimated_minutes < 60:
            time_text = f"~{estimated_minutes} min"
        else:
            hours = estimated_minutes // 60
            minutes = estimated_minutes % 60
            time_text = f"~{hours}h {minutes}m" if minutes > 0 else f"~{hours}h"
        
        distance_text = f"~{distance_miles:.1f} mi"
        
        if origin_key == "origin1":
            place["travel_time_from_origin1_text"] = time_text
            place["travel_distance_from_origin1_text"] = distance_text
        else:
            place["travel_time_from_origin2_text"] = time_text
            place["travel_distance_from_origin2_text"] = distance_text
            
    except Exception:
        # Last resort fallback
        if origin_key == "origin1":
            place["travel_time_from_origin1_text"] = "Distance unavailable"
            place["travel_distance_from_origin1_text"] = ""
        else:
            place["travel_time_from_origin2_text"] = "Distance unavailable"
            place["travel_distance_from_origin2_text"] = ""


def add_fallback_times(destinations: List[Dict[str, Any]], origin1: Dict[str, float], origin2: Dict[str, float]) -> None:
    """Add estimated times for all destinations when API completely fails."""
    for place in destinations:
        add_estimated_time(place, origin1, "origin1")
        add_estimated_time(place, origin2, "origin2")


@app.get("/api/health")
def health() -> Any:
    return {"status": "ok"}


@app.post("/api/find_midpoint")
def find_midpoint() -> Any:
    """Accepts JSON { address1, address2, placeType } and returns places near midpoint."""
    if not API_KEY:
        return jsonify({"error": "Server API key not set. Add Maps_API_KEY to backend/.env"}), 500

    data = request.get_json(silent=True) or {}
    address1 = (data.get("address1") or "").strip()
    address2 = (data.get("address2") or "").strip()
    place_type = (data.get("placeType") or "").strip()
    place_id_1 = (data.get("placeId1") or "").strip()
    place_id_2 = (data.get("placeId2") or "").strip()

    if not address1 or not address2 or not place_type:
        return jsonify({"error": "Please provide address1, address2, and placeType."}), 400

    # Prefer precise place IDs if provided; fall back to free‑text addresses
    lat1 = lng1 = lat2 = lng2 = None
    debug: Dict[str, Any] = {"a1": {}, "a2": {}}

    # Address 1
    if place_id_1:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"place_id": place_id_1, "key": API_KEY},
                timeout=15,
            )
            data1_pid = resp.json()
            debug["a1"]["place_id_status"] = data1_pid.get("status")
            debug["a1"]["place_id_error_message"] = data1_pid.get("error_message")
            if data1_pid.get("status") == "OK" and data1_pid.get("results"):
                loc = data1_pid["results"][0]["geometry"]["location"]
                lat1, lng1 = float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            debug["a1"]["place_id_exception"] = str(e)
    if lat1 is None or lng1 is None:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": address1, "key": API_KEY},
                timeout=15,
            )
            data1_addr = resp.json()
            debug["a1"]["address_status"] = data1_addr.get("status")
            debug["a1"]["address_error_message"] = data1_addr.get("error_message")
            if data1_addr.get("status") == "OK" and data1_addr.get("results"):
                loc = data1_addr["results"][0]["geometry"]["location"]
                lat1, lng1 = float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            debug["a1"]["address_exception"] = str(e)

    # Address 2
    if place_id_2:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"place_id": place_id_2, "key": API_KEY},
                timeout=15,
            )
            data2_pid = resp.json()
            debug["a2"]["place_id_status"] = data2_pid.get("status")
            debug["a2"]["place_id_error_message"] = data2_pid.get("error_message")
            if data2_pid.get("status") == "OK" and data2_pid.get("results"):
                loc = data2_pid["results"][0]["geometry"]["location"]
                lat2, lng2 = float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            debug["a2"]["place_id_exception"] = str(e)
    if lat2 is None or lng2 is None:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": address2, "key": API_KEY},
                timeout=15,
            )
            data2_addr = resp.json()
            debug["a2"]["address_status"] = data2_addr.get("status")
            debug["a2"]["address_error_message"] = data2_addr.get("error_message")
            if data2_addr.get("status") == "OK" and data2_addr.get("results"):
                loc = data2_addr["results"][0]["geometry"]["location"]
                lat2, lng2 = float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            debug["a2"]["address_exception"] = str(e)

    if None in (lat1, lng1, lat2, lng2):
        return (
            jsonify(
                {
                    "error": "Could not geocode one or both addresses.",
                    "details": debug,
                }
            ),
            400,
        )

    midpoint_lat = (lat1 + lat2) / 2.0
    midpoint_lng = (lng1 + lng2) / 2.0

    # Try progressively larger search radii around midpoint until we find places
    places = []
    search_radii = [3000, 5000, 10000, 15000, 25000]  # meters
    
    for radius in search_radii:
        places = search_places_nearby(midpoint_lat, midpoint_lng, place_type, radius_meters=radius)
        if places:
            break
    
    origin1_info = {"lat": lat1, "lng": lng1, "address": address1}
    origin2_info = {"lat": lat2, "lng": lng2, "address": address2}

    # Add driving times to all results
    add_driving_times(places, origin1_info, origin2_info)

    response_body: Dict[str, Any] = {
        "places": places,
        "origin1": origin1_info,
        "origin2": origin2_info,
        "midpoint": {"lat": midpoint_lat, "lng": midpoint_lng},
    }

    return jsonify(response_body)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


