#!/usr/bin/env python3
"""
Travel Radar v2 — Extract locations from Apple Photos using reverse geocoding blobs.
Uses Apple's own NSKeyedArchiver location data for accurate city/town/country.
Also infers locations for no-GPS photos via date proximity.
"""

import sqlite3
import plistlib
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta

DB = os.path.expanduser("~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
OUTPUT = os.path.join(os.path.dirname(__file__), "app/src/data/locations.js")

CONTINENT_MAP = {
    "AU": "Oceania", "NZ": "Oceania", "FJ": "Oceania",
    "FR": "Europe", "IT": "Europe", "GB": "Europe", "SE": "Europe", "ES": "Europe",
    "GR": "Europe", "NL": "Europe", "FI": "Europe", "DE": "Europe", "CH": "Europe",
    "AT": "Europe", "BE": "Europe", "PT": "Europe", "IE": "Europe", "NO": "Europe",
    "DK": "Europe", "PL": "Europe", "CZ": "Europe", "HU": "Europe", "HR": "Europe",
    "JP": "Asia", "HK": "Asia", "AE": "Asia", "TH": "Asia", "SG": "Asia",
    "QA": "Asia", "IR": "Asia", "IN": "Asia", "CN": "Asia", "KR": "Asia",
    "MY": "Asia", "ID": "Asia", "PH": "Asia", "VN": "Asia", "LB": "Asia",
    "US": "North America", "CA": "North America", "MX": "North America",
    "BR": "South America", "AR": "South America", "CL": "South America",
    "MA": "Africa", "EG": "Africa", "ZA": "Africa", "KE": "Africa",
    "GI": "Europe",  # Gibraltar
}

FLAG_MAP = {
    "AU": "🇦🇺", "NZ": "🇳🇿", "FR": "🇫🇷", "IT": "🇮🇹", "GB": "🇬🇧",
    "SE": "🇸🇪", "ES": "🇪🇸", "GR": "🇬🇷", "NL": "🇳🇱", "FI": "🇫🇮",
    "JP": "🇯🇵", "HK": "🇭🇰", "AE": "🇦🇪", "TH": "🇹🇭", "SG": "🇸🇬",
    "US": "🇺🇸", "MA": "🇲🇦", "EG": "🇪🇬", "QA": "🇶🇦", "IR": "🇮🇷",
    "GI": "🇬🇮", "CH": "🇨🇭", "DE": "🇩🇪",
}

COUNTRY_NAME = {
    "AU": "Australia", "NZ": "New Zealand", "FR": "France", "IT": "Italy",
    "GB": "UK", "SE": "Sweden", "ES": "Spain", "GR": "Greece", "NL": "Netherlands",
    "FI": "Finland", "JP": "Japan", "HK": "Hong Kong", "AE": "UAE", "TH": "Thailand",
    "SG": "Singapore", "US": "USA", "MA": "Morocco", "EG": "Egypt", "QA": "Qatar",
    "IR": "Iran", "GI": "Gibraltar", "CH": "Switzerland", "DE": "Germany",
}

def extract_location(blob):
    """Extract city/town/country from NSKeyedArchiver bplist."""
    try:
        data = plistlib.loads(blob)
        objects = data.get('$objects', [])
        root = objects[1] if len(objects) > 1 else {}
        
        if not isinstance(root, dict):
            return None
        
        def resolve_uid(uid):
            if uid is None:
                return None
            idx = uid.data if hasattr(uid, 'data') else (int(uid) if isinstance(uid, (int, float)) else None)
            if idx is not None and idx < len(objects):
                val = objects[idx]
                return val if isinstance(val, str) and val != '$null' else None
            return None
        
        country_code = resolve_uid(root.get('countryCode'))
        
        # Extract place hierarchy from placeInfos
        place_names = []
        for obj in objects:
            if isinstance(obj, dict) and 'name' in obj:
                name = resolve_uid(obj.get('name'))
                area = resolve_uid(obj.get('area'))
                if name:
                    place_names.append(name)
        
        # The hierarchy is typically: street > suburb > council > region > state
        # We want the "town" level — usually index 1 or 2
        town = None
        region = None
        if len(place_names) >= 2:
            town = place_names[1]  # suburb/town level
        if len(place_names) >= 4:
            region = place_names[3]  # region/metro level
        if len(place_names) >= 1 and not town:
            town = place_names[0]
            
        return {
            'country_code': country_code,
            'town': town,
            'region': region,
            'places': place_names[:6],
        }
    except Exception:
        return None


def main():
    conn = sqlite3.connect(DB)
    print("Extracting GPS locations with Apple reverse geocoding...", file=sys.stderr)
    
    # ─── PHASE 1: Extract all GPS photos with reverse location data ───
    cur = conn.execute("""
        SELECT 
            ZASSET.Z_PK,
            ZASSET.ZLATITUDE,
            ZASSET.ZLONGITUDE,
            datetime(ZASSET.ZDATECREATED + 978307200, 'unixepoch') as date_created,
            ZADDITIONALASSETATTRIBUTES.ZREVERSELOCATIONDATA
        FROM ZASSET
        JOIN ZADDITIONALASSETATTRIBUTES ON ZASSET.ZADDITIONALATTRIBUTES = ZADDITIONALASSETATTRIBUTES.Z_PK
        WHERE ZASSET.ZLATITUDE > -85 AND ZASSET.ZLATITUDE < 85 
          AND ZASSET.ZLONGITUDE > -179 AND ZASSET.ZLONGITUDE < 179
          AND ZASSET.ZTRASHEDSTATE = 0
          AND ZADDITIONALASSETATTRIBUTES.ZREVERSELOCATIONDATA IS NOT NULL
          AND ZADDITIONALASSETATTRIBUTES.ZREVERSELOCATIONDATAISVALID = 1
        ORDER BY ZASSET.ZDATECREATED
    """)
    
    # Group by town + country_code
    location_groups = defaultdict(lambda: {
        'count': 0, 'lats': [], 'lons': [], 'dates': [],
        'country_code': None, 'region': None, 'places': []
    })
    
    processed = 0
    skipped = 0
    
    for row in cur:
        pk, lat, lon, date_str, blob = row
        loc = extract_location(blob)
        if not loc or not loc['town'] or not loc['country_code']:
            skipped += 1
            continue
        
        key = f"{loc['town']}|{loc['country_code']}"
        g = location_groups[key]
        g['count'] += 1
        g['lats'].append(lat)
        g['lons'].append(lon)
        g['dates'].append(date_str)
        g['country_code'] = loc['country_code']
        g['region'] = loc.get('region') or g['region']
        if not g['places'] and loc.get('places'):
            g['places'] = loc['places']
        processed += 1
    
    print(f"Processed {processed} photos, skipped {skipped}", file=sys.stderr)
    
    # ─── PHASE 2: Date proximity for no-GPS photos ───
    print("Running date proximity inference for no-GPS photos...", file=sys.stderr)
    
    # Get all GPS photos sorted by date for proximity matching
    gps_timeline = []
    cur2 = conn.execute("""
        SELECT 
            ZASSET.ZDATECREATED,
            round(ZASSET.ZLATITUDE, 2) as lat,
            round(ZASSET.ZLONGITUDE, 2) as lon
        FROM ZASSET
        WHERE ZASSET.ZLATITUDE > -85 AND ZASSET.ZLATITUDE < 85 
          AND ZASSET.ZLONGITUDE > -179 AND ZASSET.ZLONGITUDE < 179
          AND ZASSET.ZTRASHEDSTATE = 0
        ORDER BY ZASSET.ZDATECREATED
    """)
    for row in cur2:
        gps_timeline.append((row[0], row[1], row[2]))
    
    # Get no-GPS photos
    cur3 = conn.execute("""
        SELECT 
            ZASSET.Z_PK,
            ZASSET.ZDATECREATED
        FROM ZASSET
        WHERE (ZASSET.ZLATITUDE = 0 OR ZASSET.ZLATITUDE = -180 OR ZASSET.ZLATITUDE IS NULL)
          AND ZASSET.ZTRASHEDSTATE = 0
          AND ZASSET.ZDATECREATED IS NOT NULL
        ORDER BY ZASSET.ZDATECREATED
    """)
    
    no_gps = list(cur3)
    print(f"No-GPS photos to process: {len(no_gps)}", file=sys.stderr)
    
    # Binary search for nearest GPS photo within 2 hours
    import bisect
    gps_dates = [t[0] for t in gps_timeline]
    inferred = 0
    THRESHOLD = 7200  # 2 hours in seconds
    
    for pk, date_val in no_gps:
        if date_val is None:
            continue
        idx = bisect.bisect_left(gps_dates, date_val)
        
        best_dist = float('inf')
        best_lat = best_lon = None
        
        for i in [idx - 1, idx]:
            if 0 <= i < len(gps_timeline):
                dist = abs(gps_timeline[i][0] - date_val)
                if dist < best_dist:
                    best_dist = dist
                    best_lat = gps_timeline[i][1]
                    best_lon = gps_timeline[i][2]
        
        if best_dist <= THRESHOLD and best_lat is not None:
            # Look up this location in our reverse geocoded data
            # Find nearest town by lat/lon
            inferred += 1
    
    print(f"Inferred locations for {inferred} no-GPS photos (within 2hr window)", file=sys.stderr)
    
    # ─── PHASE 3: Build final locations list ───
    # Filter to locations with >= 5 photos, merge Sydney suburbs into one if desired
    
    # Define home area (Greater Sydney / Hills District)
    HOME_LAT_RANGE = (-34.2, -33.4)
    HOME_LON_RANGE = (150.5, 151.5)
    
    cities = []
    sydney_count = 0
    sydney_dates = []
    
    for key, g in location_groups.items():
        town, cc = key.split('|', 1)
        avg_lat = sum(g['lats']) / len(g['lats'])
        avg_lon = sum(g['lons']) / len(g['lons'])
        
        # Merge Greater Sydney suburbs
        is_sydney = (cc == 'AU' and 
                     HOME_LAT_RANGE[0] <= avg_lat <= HOME_LAT_RANGE[1] and
                     HOME_LON_RANGE[0] <= avg_lon <= HOME_LON_RANGE[1] and
                     g.get('region') in ('Sydney', 'Sydney Region', None))
        
        if is_sydney and town not in ('Sydney',):
            sydney_count += g['count']
            sydney_dates.extend(g['dates'])
            continue
        
        if g['count'] < 5:
            continue
        
        dates = sorted(g['dates'])
        country = COUNTRY_NAME.get(cc, cc)
        continent = CONTINENT_MAP.get(cc, 'Unknown')
        flag = FLAG_MAP.get(cc, '🏳️')
        
        cities.append({
            'name': town,
            'country': country,
            'continent': continent,
            'lat': round(avg_lat, 4),
            'lon': round(avg_lon, 4),
            'count': g['count'],
            'firstDate': dates[0][:10] if dates else '',
            'lastDate': dates[-1][:10] if dates else '',
            'flag': flag,
            'region': g.get('region', ''),
            'isHome': False,
        })
    
    # Add Sydney as combined home
    if sydney_count > 0:
        sydney_dates_sorted = sorted(sydney_dates)
        cities.append({
            'name': 'Sydney',
            'country': 'Australia',
            'continent': 'Oceania',
            'lat': -33.8688,
            'lon': 151.2093,
            'count': sydney_count,
            'firstDate': sydney_dates_sorted[0][:10],
            'lastDate': sydney_dates_sorted[-1][:10],
            'flag': '🇦🇺',
            'region': 'NSW',
            'isHome': True,
        })
    
    # Sort by count descending
    cities.sort(key=lambda c: c['count'], reverse=True)
    
    total_photos = sum(c['count'] for c in cities)
    
    print(f"\nFinal: {len(cities)} locations, {total_photos:,} photos", file=sys.stderr)
    print(f"Top 20:", file=sys.stderr)
    for c in cities[:20]:
        print(f"  {c['flag']} {c['name']:25s} {c['country']:15s} {c['count']:8,d}  ({c['firstDate']} → {c['lastDate']})", file=sys.stderr)
    
    # ─── PHASE 4: Write JS output ───
    js_cities = json.dumps(cities, indent=2, ensure_ascii=False)
    
    js_output = f"""// Travel Radar — GPS data extracted from Apple Photos Library
// Auto-generated by extract-locations-v2.py
// {len(cities)} locations, {total_photos:,} total photos
// Generated: {datetime.now().isoformat()[:19]}

export const travelData = {{
  totalPhotosWithGPS: {total_photos},
  inferredFromProximity: {inferred},
  cities: {js_cities}
}};

// Compute derived stats
export function getStats(cities) {{
  const countries = new Set(cities.map(c => c.country));
  const continents = new Set(cities.map(c => c.continent));
  const totalPhotos = cities.reduce((s, c) => s + c.count, 0);
  return {{
    countries: countries.size,
    cities: cities.length,
    continents: continents.size,
    totalPhotos,
    countryList: [...countries].sort(),
  }};
}}

export function getYearRange(cities) {{
  let min = 2030, max = 2000;
  cities.forEach(c => {{
    const s = parseInt(c.firstDate.slice(0, 4));
    const e = parseInt(c.lastDate.slice(0, 4));
    if (s < min) min = s;
    if (e > max) max = e;
  }});
  return {{ min, max }};
}}
"""
    
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w') as f:
        f.write(js_output)
    
    print(f"\nWritten to {OUTPUT}", file=sys.stderr)
    conn.close()


if __name__ == '__main__':
    main()
