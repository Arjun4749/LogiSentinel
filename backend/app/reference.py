"""Static reference data for the demonstration network (pan-India).

All node names are fictional code names placed on public geography purely for
demonstration. No real unit, deployment or operational data is used.
"""
from __future__ import annotations

CATEGORIES = {
    "RATIONS": {"name": "Rations", "unit": "kg", "kg_per_unit": 1.0, "per_person_day": 1.6,
                "criticality": 0.95, "color": "#d9a21b"},
    "WATER": {"name": "Drinking Water", "unit": "L", "kg_per_unit": 1.0, "per_person_day": 8.0,
              "criticality": 0.97, "color": "#2f8fd8"},
    "FUEL": {"name": "Fuel (POL)", "unit": "L", "kg_per_unit": 0.85, "per_person_day": 5.5,
             "criticality": 0.90, "color": "#e2701f"},
    "MEDICAL": {"name": "Medical Supplies", "unit": "kits", "kg_per_unit": 2.5, "per_person_day": 0.02,
                "criticality": 1.00, "color": "#cf3b3b"},
    "AMMO": {"name": "Ammunition", "unit": "boxes", "kg_per_unit": 22.0, "per_person_day": 0.015,
             "criticality": 0.85, "color": "#7f5bd6"},
    "SPARES": {"name": "Vehicle Spares", "unit": "parts", "kg_per_unit": 4.0, "per_person_day": 0.03,
               "criticality": 0.55, "color": "#3a86c8"},
    "WINTER": {"name": "Winter Clothing", "unit": "sets", "kg_per_unit": 5.0, "per_person_day": 0.01,
               "criticality": 0.75, "color": "#2fa6b0"},
}

SECTORS = {
    "NORTH": {"name": "Northern sector", "short": "North", "desc": "High-altitude mountains and snow passes",
              "center": [33.4, 76.6], "zoom": 7},
    "EAST": {"name": "Eastern sector", "short": "East", "desc": "North-east hills, heavy rain and landslides",
             "center": [27.2, 90.8], "zoom": 7},
    "WEST": {"name": "Western sector", "short": "West", "desc": "Thar desert, heat and dust storms",
             "center": [26.6, 72.1], "zoom": 7},
    "ISLANDS": {"name": "Island sector", "short": "Islands", "desc": "Bay of Bengal islands, sea and air supply",
                "center": [11.6, 87.0], "zoom": 6},
}

# type: depot (rail-head / port base), hub (forward supply hub), post (forward post)
NODES = {
    # ---------------- Northern sector ----------------
    "DEP-A": {"name": "Base Depot Alpha", "type": "depot", "sector": "NORTH", "lat": 30.73, "lon": 76.78, "alt": 350,
              "terrain": "Plains", "personnel": 1200, "helipad": True, "airfield": True, "parent": None},
    "DEP-B": {"name": "Base Depot Bravo", "type": "depot", "sector": "NORTH", "lat": 32.27, "lon": 75.65, "alt": 330,
              "terrain": "Plains", "personnel": 900, "helipad": True, "airfield": True, "parent": None},
    "HUB-K": {"name": "Supply Hub Kilo", "type": "hub", "sector": "NORTH", "lat": 34.08, "lon": 74.80, "alt": 1585,
              "terrain": "Valley", "personnel": 800, "helipad": True, "airfield": True, "parent": "DEP-B"},
    "HUB-L": {"name": "Supply Hub Lima", "type": "hub", "sector": "NORTH", "lat": 34.16, "lon": 77.58, "alt": 3500,
              "terrain": "High Altitude", "personnel": 900, "helipad": True, "airfield": True, "parent": "DEP-B"},
    "HUB-M": {"name": "Supply Hub Mike", "type": "hub", "sector": "NORTH", "lat": 32.24, "lon": 77.19, "alt": 2050,
              "terrain": "Mountain", "personnel": 500, "helipad": True, "airfield": False, "parent": "DEP-A"},
    "FP-E": {"name": "Post Echo", "type": "post", "sector": "NORTH", "lat": 34.43, "lon": 75.76, "alt": 3280,
             "terrain": "High Altitude", "personnel": 180, "helipad": True, "airfield": False, "parent": "HUB-K"},
    "FP-F": {"name": "Post Foxtrot", "type": "post", "sector": "NORTH", "lat": 34.55, "lon": 76.13, "alt": 2680,
             "terrain": "Mountain", "personnel": 220, "helipad": True, "airfield": False, "parent": "HUB-K"},
    "FP-G": {"name": "Post Golf", "type": "post", "sector": "NORTH", "lat": 34.63, "lon": 74.84, "alt": 2400,
             "terrain": "Snow-bound", "personnel": 140, "helipad": True, "airfield": False, "parent": "HUB-K"},
    "FP-H": {"name": "Post Hotel", "type": "post", "sector": "NORTH", "lat": 34.55, "lon": 77.56, "alt": 3140,
             "terrain": "High Altitude", "personnel": 160, "helipad": True, "airfield": False, "parent": "HUB-L"},
    "FP-I": {"name": "Post India", "type": "post", "sector": "NORTH", "lat": 33.20, "lon": 78.65, "alt": 4180,
             "terrain": "Super High Altitude", "personnel": 200, "helipad": True, "airfield": False, "parent": "HUB-L"},
    "FP-J": {"name": "Post Juliet", "type": "post", "sector": "NORTH", "lat": 32.23, "lon": 78.07, "alt": 3800,
             "terrain": "Snow-bound", "personnel": 120, "helipad": True, "airfield": False, "parent": "HUB-M"},
    # ---------------- Eastern sector ----------------
    "DEP-C": {"name": "Base Depot Charlie", "type": "depot", "sector": "EAST", "lat": 26.73, "lon": 88.40, "alt": 120,
              "terrain": "Plains", "personnel": 1000, "helipad": True, "airfield": True, "parent": None},
    "HUB-N": {"name": "Supply Hub November", "type": "hub", "sector": "EAST", "lat": 27.33, "lon": 88.61, "alt": 1650,
              "terrain": "Mountain", "personnel": 600, "helipad": True, "airfield": False, "parent": "DEP-C"},
    "HUB-O": {"name": "Supply Hub Oscar", "type": "hub", "sector": "EAST", "lat": 26.63, "lon": 92.80, "alt": 80,
              "terrain": "Valley", "personnel": 700, "helipad": True, "airfield": True, "parent": "DEP-C"},
    "FP-R": {"name": "Post Romeo", "type": "post", "sector": "EAST", "lat": 27.69, "lon": 88.74, "alt": 2900,
             "terrain": "High Altitude", "personnel": 150, "helipad": True, "airfield": False, "parent": "HUB-N"},
    "FP-S": {"name": "Post Sierra", "type": "post", "sector": "EAST", "lat": 27.36, "lon": 92.24, "alt": 1500,
             "terrain": "Mountain", "personnel": 170, "helipad": True, "airfield": False, "parent": "HUB-O"},
    "FP-T": {"name": "Post Tango", "type": "post", "sector": "EAST", "lat": 27.54, "lon": 93.83, "alt": 1700,
             "terrain": "Jungle", "personnel": 130, "helipad": True, "airfield": False, "parent": "HUB-O"},
    # ---------------- Western sector ----------------
    "DEP-D": {"name": "Base Depot Delta", "type": "depot", "sector": "WEST", "lat": 26.24, "lon": 73.02, "alt": 230,
              "terrain": "Desert", "personnel": 1100, "helipad": True, "airfield": True, "parent": None},
    "HUB-P": {"name": "Supply Hub Papa", "type": "hub", "sector": "WEST", "lat": 26.91, "lon": 70.91, "alt": 225,
              "terrain": "Desert", "personnel": 700, "helipad": True, "airfield": True, "parent": "DEP-D"},
    "FP-V": {"name": "Post Victor", "type": "post", "sector": "WEST", "lat": 26.92, "lon": 71.92, "alt": 230,
             "terrain": "Desert", "personnel": 240, "helipad": True, "airfield": False, "parent": "HUB-P"},
    "FP-W": {"name": "Post Whiskey", "type": "post", "sector": "WEST", "lat": 25.75, "lon": 71.39, "alt": 200,
             "terrain": "Desert", "personnel": 210, "helipad": True, "airfield": False, "parent": "HUB-P"},
    "FP-X": {"name": "Post X-ray", "type": "post", "sector": "WEST", "lat": 28.02, "lon": 73.31, "alt": 240,
             "terrain": "Desert", "personnel": 190, "helipad": True, "airfield": False, "parent": "DEP-D"},
    # ---------------- Island sector ----------------
    "DEP-Y": {"name": "Port Depot Yankee", "type": "depot", "sector": "ISLANDS", "lat": 13.08, "lon": 80.29, "alt": 10,
              "terrain": "Coastal", "personnel": 900, "helipad": True, "airfield": True, "parent": None},
    "HUB-Q": {"name": "Island Hub Quebec", "type": "hub", "sector": "ISLANDS", "lat": 11.62, "lon": 92.73, "alt": 20,
              "terrain": "Island", "personnel": 600, "helipad": True, "airfield": True, "parent": "DEP-Y"},
    "FP-Z": {"name": "Post Zulu", "type": "post", "sector": "ISLANDS", "lat": 9.16, "lon": 92.82, "alt": 10,
             "terrain": "Island", "personnel": 160, "helipad": True, "airfield": False, "parent": "HUB-Q"},
    "FP-U": {"name": "Post Uniform", "type": "post", "sector": "ISLANDS", "lat": 13.27, "lon": 93.00, "alt": 30,
             "terrain": "Island", "personnel": 140, "helipad": True, "airfield": False, "parent": "HUB-Q"},
}

# Road and sea network. Waypoints are only for drawing nicer lines on the map.
_R = dict(mode="ROAD", snow_prone=False, landslide_prone=False, wp=[])
ROUTES = {
    # North
    "R1": {**_R, "a": "DEP-A", "b": "DEP-B", "name": "Plains Highway", "km": 250, "speed": 45, "base_risk": 5,
           "max_alt": 600, "on_time_rate": 0.96},
    "R2": {**_R, "a": "DEP-B", "b": "HUB-K", "name": "Valley Highway (Tunnel Route)", "km": 330, "speed": 30,
           "base_risk": 14, "landslide_prone": True, "max_alt": 2200, "on_time_rate": 0.86,
           "wp": [[32.73, 74.86], [33.25, 75.24], [33.6, 75.1]]},
    "R3": {**_R, "a": "DEP-A", "b": "HUB-M", "name": "Hill Highway South", "km": 310, "speed": 30, "base_risk": 12,
           "landslide_prone": True, "max_alt": 2050, "on_time_rate": 0.88, "wp": [[31.30, 76.85], [31.71, 76.93]]},
    "R4": {**_R, "a": "HUB-K", "b": "FP-E", "name": "Zoji Pass Road", "km": 145, "speed": 22, "base_risk": 25,
           "snow_prone": True, "landslide_prone": True, "max_alt": 3530, "on_time_rate": 0.74,
           "wp": [[34.30, 75.29], [34.28, 75.47]]},
    "R5": {**_R, "a": "FP-E", "b": "FP-F", "name": "Echo-Foxtrot Link", "km": 60, "speed": 30, "base_risk": 10,
           "max_alt": 3300, "on_time_rate": 0.92},
    "R6": {**_R, "a": "FP-F", "b": "HUB-L", "name": "Western Ladder Road", "km": 220, "speed": 28, "base_risk": 15,
           "landslide_prone": True, "max_alt": 4100, "on_time_rate": 0.87, "wp": [[34.28, 76.77], [34.20, 77.20]]},
    "R7": {**_R, "a": "HUB-M", "b": "HUB-L", "name": "High Passes Highway", "km": 475, "speed": 20, "base_risk": 30,
           "snow_prone": True, "landslide_prone": True, "max_alt": 5300, "on_time_rate": 0.70,
           "wp": [[32.37, 77.25], [32.57, 77.03], [32.76, 77.42], [32.90, 77.57], [33.50, 77.77]]},
    "R8": {**_R, "a": "HUB-K", "b": "FP-G", "name": "Razdan Pass Road", "km": 125, "speed": 20, "base_risk": 25,
           "snow_prone": True, "max_alt": 3300, "on_time_rate": 0.76, "wp": [[34.36, 74.65], [34.55, 74.72]]},
    "R9": {**_R, "a": "HUB-L", "b": "FP-H", "name": "Khardung Pass Road", "km": 120, "speed": 20, "base_risk": 22,
           "snow_prone": True, "max_alt": 5350, "on_time_rate": 0.80, "wp": [[34.28, 77.60], [34.40, 77.62]]},
    "R10": {**_R, "a": "HUB-L", "b": "FP-I", "name": "Indus Valley Road", "km": 180, "speed": 25, "base_risk": 18,
            "landslide_prone": True, "max_alt": 4300, "on_time_rate": 0.84, "wp": [[33.83, 77.81], [33.36, 78.33]]},
    "R11": {**_R, "a": "HUB-M", "b": "FP-J", "name": "Kunzum Pass Road", "km": 200, "speed": 18, "base_risk": 25,
            "snow_prone": True, "landslide_prone": True, "max_alt": 4550, "on_time_rate": 0.75,
            "wp": [[32.37, 77.25], [32.40, 77.63]]},
    "R12": {**_R, "a": "DEP-B", "b": "HUB-M", "name": "Foothills Highway", "km": 260, "speed": 32, "base_risk": 10,
            "landslide_prone": True, "max_alt": 2050, "on_time_rate": 0.90, "wp": [[32.22, 76.32], [31.71, 76.93]]},
    # East
    "R13": {**_R, "a": "DEP-C", "b": "HUB-N", "name": "Teesta Valley Highway", "km": 115, "speed": 25, "base_risk": 18,
            "landslide_prone": True, "max_alt": 1700, "on_time_rate": 0.82, "wp": [[26.90, 88.47], [27.10, 88.47]]},
    "R14": {**_R, "a": "HUB-N", "b": "FP-R", "name": "North Valley Road", "km": 120, "speed": 18, "base_risk": 24,
            "snow_prone": True, "landslide_prone": True, "max_alt": 3000, "on_time_rate": 0.77,
            "wp": [[27.45, 88.55], [27.60, 88.65]]},
    "R15": {**_R, "a": "DEP-C", "b": "HUB-O", "name": "Brahmaputra Corridor", "km": 420, "speed": 40, "base_risk": 10,
            "max_alt": 300, "on_time_rate": 0.90, "wp": [[26.50, 89.60], [26.20, 91.00], [26.40, 92.00]]},
    "R16": {**_R, "a": "HUB-O", "b": "FP-S", "name": "Kameng Ridge Road", "km": 160, "speed": 20, "base_risk": 22,
            "landslide_prone": True, "max_alt": 2750, "on_time_rate": 0.79, "wp": [[26.95, 92.60], [27.26, 92.42]]},
    "R17": {**_R, "a": "HUB-O", "b": "FP-T", "name": "Subansiri Road", "km": 330, "speed": 24, "base_risk": 20,
            "landslide_prone": True, "max_alt": 1800, "on_time_rate": 0.80, "wp": [[26.90, 93.50], [27.23, 94.10]]},
    # West
    "R18": {**_R, "a": "DEP-D", "b": "HUB-P", "name": "Desert Highway", "km": 285, "speed": 45, "base_risk": 8,
            "max_alt": 300, "on_time_rate": 0.94, "wp": [[26.60, 72.10]]},
    "R19": {**_R, "a": "HUB-P", "b": "FP-V", "name": "Dune Track East", "km": 110, "speed": 35, "base_risk": 12,
            "max_alt": 300, "on_time_rate": 0.90},
    "R20": {**_R, "a": "HUB-P", "b": "FP-W", "name": "Southern Desert Road", "km": 155, "speed": 38, "base_risk": 12,
            "max_alt": 300, "on_time_rate": 0.91, "wp": [[26.30, 71.10]]},
    "R21": {**_R, "a": "DEP-D", "b": "FP-X", "name": "Northern Desert Highway", "km": 250, "speed": 45, "base_risk": 8,
            "max_alt": 300, "on_time_rate": 0.94, "wp": [[27.10, 73.20]]},
    # Islands (sea lanes + island trunk road)
    "S1": {**_R, "mode": "SEA", "a": "DEP-Y", "b": "HUB-Q", "name": "Bay of Bengal Sea Lane", "km": 1350, "speed": 26,
           "base_risk": 15, "max_alt": 0, "on_time_rate": 0.85, "wp": [[12.6, 84.0], [12.0, 88.5]]},
    "S2": {**_R, "mode": "SEA", "a": "HUB-Q", "b": "FP-Z", "name": "Ten Degree Channel Lane", "km": 280, "speed": 22,
           "base_risk": 18, "max_alt": 0, "on_time_rate": 0.82, "wp": [[10.6, 92.9]]},
    "R22": {**_R, "a": "HUB-Q", "b": "FP-U", "name": "Island Trunk Road", "km": 300, "speed": 28, "base_risk": 14,
            "landslide_prone": True, "max_alt": 300, "on_time_rate": 0.86, "wp": [[12.20, 92.85], [12.80, 92.95]]},
}

ASSET_TYPES = {
    "HEAVY_TRUCK": {"name": "Heavy Truck (10 t)", "capacity_kg": 10000, "mode": "ROAD", "speed_factor": 1.0,
                    "cost_per_km": 38, "categories": None},
    "LIGHT_TRUCK": {"name": "Light Truck (3 t)", "capacity_kg": 3000, "mode": "ROAD", "speed_factor": 1.15,
                    "cost_per_km": 22, "categories": None},
    "TANKER": {"name": "Tanker (12 kL)", "capacity_kg": 10200, "mode": "ROAD", "speed_factor": 0.95,
               "cost_per_km": 42, "categories": ["FUEL", "WATER"]},
    "HELICOPTER": {"name": "Medium Helicopter (3 t)", "capacity_kg": 3000, "mode": "AIR", "speed_kmh": 200,
                   "cost_per_km": 450, "categories": None, "range_km": 450, "needs": "helipad"},
    "AIRCRAFT": {"name": "Transport Aircraft (8 t)", "capacity_kg": 8000, "mode": "AIR", "speed_kmh": 450,
                 "cost_per_km": 650, "categories": None, "range_km": 2500, "needs": "airfield"},
    "DRONE": {"name": "Logistics Drone (40 kg)", "capacity_kg": 40, "mode": "DRONE", "speed_kmh": 90,
              "cost_per_km": 15, "categories": ["MEDICAL", "SPARES"], "range_km": 130},
    "SHIP": {"name": "Landing Ship (500 t)", "capacity_kg": 500000, "mode": "SEA", "speed_factor": 1.0,
             "cost_per_km": 900, "categories": None},
    "CRAFT": {"name": "Landing Craft (60 t)", "capacity_kg": 60000, "mode": "SEA", "speed_factor": 0.9,
              "cost_per_km": 300, "categories": None},
}

ASSETS = [
    # North
    ("TRK-01", "HEAVY_TRUCK", "DEP-A"), ("TRK-02", "HEAVY_TRUCK", "DEP-A"),
    ("TRK-03", "HEAVY_TRUCK", "DEP-B"), ("TRK-04", "HEAVY_TRUCK", "DEP-B"),
    ("TRK-05", "HEAVY_TRUCK", "HUB-K"), ("TRK-06", "HEAVY_TRUCK", "HUB-L"),
    ("TRK-07", "HEAVY_TRUCK", "HUB-M"),
    ("LTV-01", "LIGHT_TRUCK", "HUB-K"), ("LTV-02", "LIGHT_TRUCK", "HUB-K"),
    ("LTV-03", "LIGHT_TRUCK", "HUB-L"), ("LTV-04", "LIGHT_TRUCK", "HUB-L"),
    ("LTV-05", "LIGHT_TRUCK", "HUB-M"),
    ("TNK-01", "TANKER", "DEP-B"), ("TNK-02", "TANKER", "HUB-L"), ("TNK-03", "TANKER", "HUB-K"),
    ("HEL-01", "HELICOPTER", "HUB-L"), ("HEL-02", "HELICOPTER", "HUB-K"),
    ("UAV-01", "DRONE", "HUB-K"), ("UAV-02", "DRONE", "HUB-L"),
    ("AC-01", "AIRCRAFT", "DEP-A"),
    # East
    ("TRK-08", "HEAVY_TRUCK", "DEP-C"), ("TRK-09", "HEAVY_TRUCK", "HUB-O"),
    ("LTV-06", "LIGHT_TRUCK", "HUB-N"), ("LTV-07", "LIGHT_TRUCK", "HUB-O"),
    ("TNK-04", "TANKER", "DEP-C"), ("HEL-03", "HELICOPTER", "HUB-O"), ("UAV-03", "DRONE", "HUB-N"),
    # West
    ("TRK-10", "HEAVY_TRUCK", "DEP-D"), ("TRK-11", "HEAVY_TRUCK", "HUB-P"),
    ("LTV-08", "LIGHT_TRUCK", "HUB-P"), ("TNK-05", "TANKER", "HUB-P"), ("TNK-06", "TANKER", "DEP-D"),
    ("TRK-12", "HEAVY_TRUCK", "DEP-D"), ("LTV-10", "LIGHT_TRUCK", "HUB-P"), ("HEL-05", "HELICOPTER", "HUB-P"),
    # Islands
    ("SHIP-01", "SHIP", "DEP-Y"), ("SHIP-02", "SHIP", "DEP-Y"), ("CRAFT-01", "CRAFT", "HUB-Q"),
    ("LTV-09", "LIGHT_TRUCK", "HUB-Q"), ("HEL-04", "HELICOPTER", "HUB-Q"), ("AC-02", "AIRCRAFT", "DEP-Y"),
]

USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "Col. R. Mehta", "title": "Logistics Commander"},
    "planner": {"password": "planner123", "role": "planner", "name": "Maj. A. Verma", "title": "Supply Planner"},
    "viewer": {"password": "viewer123", "role": "viewer", "name": "Capt. S. Iyer", "title": "Staff Observer"},
}

ROLE_RANK = {"viewer": 0, "planner": 1, "admin": 2}
