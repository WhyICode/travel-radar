#!/usr/bin/env python3
"""
Extract sub-locations (POIs, neighborhoods, attractions) per city for drill-down view.
Uses Apple's reverse geocoding hierarchy: street → POI → neighborhood → suburb → city.
"""

import sqlite3
import plistlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

DB = os.path.expanduser("~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
OUTPUT = os.path.join(os.path.dirname(__file__), "app/src/data/sublocs.js")

# Same Sydney merge set from v3
SYDNEY_MERGE = set()  # Will load from extract script
TOKYO_MERGE = {'Shibuya', 'Shinjuku', 'Taito', 'Chiyoda', 'Minato', 'Chuo',
    'Meguro', 'Shinagawa', 'Ota', 'Setagaya', 'Suginami', 'Nakano',
    'Toshima', 'Kita', 'Itabashi', 'Nerima', 'Bunkyo', 'Sumida',
    'Koto', 'Edogawa', 'Arakawa', 'Adachi', 'Katsushika'}

RENAME_MAP = {
    'Chessy': 'Disneyland Paris', 'Bailly-Romainvilliers': 'Disneyland Paris',
    'Villeneuve-le-Comte': 'Disneyland Paris', 'Bay Lake': 'Walt Disney World',
    'Amphoe Bang Phli': 'Bangkok', 'Bang Phli District': 'Bangkok',
    'Chek Lap Kok': 'Hong Kong', 'Hounslow': 'Heathrow Airport',
    'Stockholm-Arlanda': 'Stockholm', 'Tremblay-en-France': 'Paris CDG Airport',
    'Deira Islands': 'Dubai', 'Pukaki Ward': 'Mt Cook',
    'Queenstown-Wakatipu Ward': 'Queenstown', 'Vantaa': 'Helsinki',
    'Romford': 'London', 'Fujiyoshida': 'Mt Fuji',
}


def extract_hierarchy(blob):
    """Extract full place hierarchy from NSKeyedArchiver bplist."""
    try:
        data = plistlib.loads(blob)
        objects = data.get('$objects', [])
        
        def resolve(uid):
            if uid is None: return None
            idx = uid.data if hasattr(uid, 'data') else (int(uid) if isinstance(uid, (int, float)) else None)
            if idx and 0 < idx < len(objects):
                val = objects[idx]
                return val if isinstance(val, str) and val != '$null' else None
            return None
        
        # Get postal address
        city = sub_locality = country_code = None
        for obj in objects:
            if isinstance(obj, dict) and '_city' in obj and '_ISOCountryCode' in obj:
                city = resolve(obj.get('_city'))
                sub_locality = resolve(obj.get('_subLocality'))
                country_code = resolve(obj.get('_ISOCountryCode'))
                break
        
        # Get place names hierarchy (POIs, streets, neighborhoods)
        places = []
        for obj in objects:
            if isinstance(obj, dict) and 'name' in obj and 'placeType' in obj:
                name = resolve(obj.get('name'))
                if name:
                    places.append(name)
        
        # places[0] is usually the most specific (POI/street)
        # places[1] is neighborhood/suburb
        poi = places[0] if len(places) > 0 else None
        neighborhood = places[1] if len(places) > 1 else sub_locality
        
        return {
            'city': city,
            'country_code': country_code,
            'poi': poi,
            'neighborhood': neighborhood or sub_locality,
            'sub_locality': sub_locality,
        }
    except Exception:
        return None


def main():
    conn = sqlite3.connect(DB)
    CORE_EPOCH = 978307200
    
    print("Extracting sub-locations per city...", file=sys.stderr)
    
    # Load Sydney merge list from the main script
    # For simplicity, just detect by lat/lon range
    
    cur = conn.execute("""
        SELECT 
            ZASSET.ZLATITUDE,
            ZASSET.ZLONGITUDE,
            ZASSET.ZDATECREATED,
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
    
    # city_key → { subloc_name → { count, lat, lon, dates, type } }
    city_sublocs = defaultdict(lambda: defaultdict(lambda: {
        'count': 0, 'lats': [], 'lons': [], 'dates': [], 'type': 'poi'
    }))
    
    processed = 0
    for lat, lon, date_val, blob in cur:
        h = extract_hierarchy(blob)
        if not h or not h.get('city') or not h.get('country_code'):
            continue
        
        cc = h['country_code']
        city = h['city']
        
        # Apply same merges as main script
        if cc == 'AU' and -34.2 <= lat <= -33.4 and 150.5 <= lon <= 151.5:
            # Check if it's a Sydney suburb — simplified check
            city = 'Sydney'
        if cc == 'JP' and city in TOKYO_MERGE:
            city = 'Tokyo'
        if city in RENAME_MAP:
            city = RENAME_MAP[city]
        
        city_key = f"{city}|{cc}"
        
        # Add POI as sub-location
        poi = h.get('poi')
        neighborhood = h.get('neighborhood')
        
        # Use POI if it's interesting (not just a street address)
        subloc_name = poi or neighborhood
        if not subloc_name:
            continue
        
        # Skip generic/boring entries
        if subloc_name in (city, cc, 'Australia', 'New South Wales', 'NSW'):
            continue
        
        s = city_sublocs[city_key][subloc_name]
        s['count'] += 1
        s['lats'].append(lat)
        s['lons'].append(lon)
        if date_val:
            s['dates'].append(date_val)
        
        # Classify type
        if neighborhood and neighborhood == subloc_name:
            s['type'] = 'neighborhood'
        
        processed += 1
    
    print(f"Processed {processed:,} photos into sub-locations", file=sys.stderr)
    
    # Build output: only cities with interesting sub-locations
    result = {}
    for city_key, sublocs in city_sublocs.items():
        city_name = city_key.split('|')[0]
        
        # Filter to sublocs with >= 3 photos, take top 50
        filtered = []
        for name, data in sublocs.items():
            if data['count'] < 3:
                continue
            avg_lat = sum(data['lats']) / len(data['lats'])
            avg_lon = sum(data['lons']) / len(data['lons'])
            dates = sorted(data['dates'])
            
            first = datetime.utcfromtimestamp(dates[0] + CORE_EPOCH).strftime('%Y-%m-%d') if dates else ''
            last = datetime.utcfromtimestamp(dates[-1] + CORE_EPOCH).strftime('%Y-%m-%d') if dates else ''
            
            filtered.append({
                'name': name,
                'count': data['count'],
                'lat': round(avg_lat, 5),
                'lon': round(avg_lon, 5),
                'firstDate': first,
                'lastDate': last,
                'type': data['type'],
            })
        
        filtered.sort(key=lambda x: x['count'], reverse=True)
        
        if len(filtered) >= 2:  # Only include cities with 2+ sub-locations
            result[city_key] = filtered[:50]
    
    # Print summary
    print(f"\n{len(result)} cities with drill-down data:", file=sys.stderr)
    for key in sorted(result, key=lambda k: sum(s['count'] for s in result[k]), reverse=True)[:15]:
        city = key.split('|')[0]
        sublocs = result[key]
        total = sum(s['count'] for s in sublocs)
        print(f"  {city:25s} {len(sublocs):3d} locations, {total:>7,d} photos", file=sys.stderr)
        for s in sublocs[:5]:
            print(f"    {s['name'][:40]:40s} {s['count']:>5,d}", file=sys.stderr)
    
    # Write JS
    js = f"""// Travel Radar — Sub-location data for city drill-down
// Generated: {datetime.now().isoformat()[:19]}
// {len(result)} cities with drill-down data

export const subLocations = {json.dumps(result, indent=2, ensure_ascii=False)};
"""
    
    with open(OUTPUT, 'w') as f:
        f.write(js)
    
    print(f"\n✅ Written to {OUTPUT}", file=sys.stderr)
    conn.close()

if __name__ == '__main__':
    main()
