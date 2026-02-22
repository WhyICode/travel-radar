#!/usr/bin/env python3
"""
Travel Radar v3 — Uses Apple's CNPostalAddress from reverse geocoding for accurate city/country.
Groups by _city + _ISOCountryCode from the postalAddress NSKeyedArchiver blob.
Merges Greater Sydney. Date-proximity inference for no-GPS photos.
"""

import sqlite3
import plistlib
import json
import os
import sys
import bisect
from collections import defaultdict
from datetime import datetime

DB = os.path.expanduser("~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
OUTPUT = os.path.join(os.path.dirname(__file__), "app/src/data/locations.js")

CONTINENT_MAP = {
    "AU": "Oceania", "NZ": "Oceania", "FJ": "Oceania",
    "FR": "Europe", "IT": "Europe", "GB": "Europe", "SE": "Europe", "ES": "Europe",
    "GR": "Europe", "NL": "Europe", "FI": "Finland", "DE": "Europe", "CH": "Europe",
    "AT": "Europe", "BE": "Europe", "PT": "Europe", "IE": "Europe", "NO": "Europe",
    "DK": "Europe", "MC": "Europe", "HR": "Europe",
    "JP": "Asia", "HK": "Asia", "AE": "Asia", "TH": "Asia", "SG": "Asia",
    "QA": "Asia", "IR": "Asia", "IN": "Asia", "CN": "Asia", "KR": "Asia",
    "LB": "Asia", "JO": "Asia", "TR": "Asia",
    "US": "North America", "CA": "North America", "MX": "North America",
    "BR": "South America", "AR": "South America",
    "MA": "Africa", "EG": "Africa", "ZA": "Africa",
    "GI": "Europe", "IN": "Asia",
}

FLAG_MAP = {
    "AU": "🇦🇺", "NZ": "🇳🇿", "FR": "🇫🇷", "IT": "🇮🇹", "GB": "🇬🇧",
    "SE": "🇸🇪", "ES": "🇪🇸", "GR": "🇬🇷", "NL": "🇳🇱", "FI": "🇫🇮",
    "JP": "🇯🇵", "HK": "🇭🇰", "AE": "🇦🇪", "TH": "🇹🇭", "SG": "🇸🇬",
    "US": "🇺🇸", "MA": "🇲🇦", "EG": "🇪🇬", "QA": "🇶🇦", "IR": "🇮🇷",
    "GI": "🇬🇮", "CH": "🇨🇭", "DE": "🇩🇪", "MC": "🇲🇨", "HR": "🇭🇷",
    "LB": "🇱🇧", "JO": "🇯🇴", "TR": "🇹🇷", "IN": "🇮🇳",
}

COUNTRY_NAME = {
    "AU": "Australia", "NZ": "New Zealand", "FR": "France", "IT": "Italy",
    "GB": "UK", "SE": "Sweden", "ES": "Spain", "GR": "Greece", "NL": "Netherlands",
    "FI": "Finland", "JP": "Japan", "HK": "Hong Kong", "AE": "UAE", "TH": "Thailand",
    "SG": "Singapore", "US": "USA", "MA": "Morocco", "EG": "Egypt", "QA": "Qatar",
    "IR": "Iran", "GI": "Gibraltar", "CH": "Switzerland", "DE": "Germany",
    "MC": "Monaco", "HR": "Croatia", "LB": "Lebanon", "JO": "Jordan", "TR": "Turkey",
    "IN": "India",
}

# Sydney metro — merge these into "Sydney"
SYDNEY_MERGE = {
    'Bella Vista', 'Castle Hill', 'Kellyville', 'Rouse Hill', 'Baulkham Hills',
    'Parramatta', 'Blacktown', 'Penrith', 'Liverpool', 'Campbelltown', 'Camden',
    'Hornsby', 'Epping', 'Chatswood', 'North Sydney', 'Manly', 'Dee Why',
    'Bondi', 'Maroubra', 'Sutherland', 'Cronulla', 'Strathfield', 'Burwood',
    'Bankstown', 'Fairfield', 'Auburn', 'Granville', 'Toongabbie', 'Merrylands',
    'Rooty Hill', 'Mount Druitt', 'Seven Hills', 'Dural', 'Galston',
    'Winston Hills', 'Northmead', 'Wentworthville', 'Westmead', 'Marsden Park',
    'Prairiewood', 'Cabramatta', 'Glenwood', 'Stanhope Gardens', 'The Ponds',
    'Schofields', 'Quakers Hill', 'Riverstone', 'Box Hill', 'Vineyard',
    'Constitution Hill', 'Dundas', 'Ermington', 'Rydalmere', 'Carlingford',
    'Beecroft', 'Cheltenham', 'Pennant Hills', 'Thornleigh', 'Wahroonga',
    'Turramurra', 'St Ives', 'Gordon', 'Pymble', 'Lindfield', 'Killara',
    'Artarmon', 'Lane Cove', 'Willoughby', 'Mosman', 'Neutral Bay',
    'Kurnell', 'Sans Souci', 'Hurstville', 'Kogarah', 'Rockdale',
    'Mascot', 'Botany', 'Redfern', 'Surry Hills', 'Darlinghurst', 'Potts Point',
    'Paddington', 'Woollahra', 'Double Bay', 'Rose Bay', 'Vaucluse',
    'Bonnet Bay', 'Engadine', 'Menai', 'Jannali', 'Caringbah',
    'North Strathfield', 'Concord', 'Five Dock', 'Leichhardt', 'Newtown',
    'Marrickville', 'Dulwich Hill', 'Canterbury', 'Lakemba', 'Punchbowl',
    'Revesby', 'Padstow', 'East Hills', 'Panania', 'Milperra',
    'Harrington Park', 'Gledswood Hills', 'Gregory Hills', 'Oran Park',
    'Leppington', 'Edmondson Park', 'Moorebank', 'Wattle Grove',
    'Homebush', 'Olympic Park', 'Rhodes', 'Wentworth Point',
    'La Perouse', 'Little Bay', 'Malabar', 'Coogee', 'Randwick',
    'Waverton', 'McMahons Point', 'Kirribilli', 'Milsons Point',
    # Additional Sydney suburbs/venues
    'Sydney Olympic Park', 'Norwest', 'Barangaroo', 'Alexandria', 'The Rocks',
    'Darling Harbour', 'Haymarket', 'Ultimo', 'Pyrmont', 'Glebe',
    'Balmain', 'Rozelle', 'Annandale', 'Stanmore', 'Petersham',
    'Summer Hill', 'Ashfield', 'Croydon', 'Burwood Heights',
    'Homebush West', 'Lidcombe', 'Berala', 'Regents Park', 'Sefton',
    'Chester Hill', 'Bass Hill', 'Villawood', 'Carramar', 'Lansdowne',
    'Canley Vale', 'Canley Heights', 'Cabramatta West', 'Bonnyrigg',
    'St Johns Park', 'Wakeley', 'Smithfield', 'Wetherill Park',
    'Greystanes', 'Pemulwuy', 'Prospect', 'Girraween', 'Pendle Hill',
    'Homebush Bay', 'Silverwater', 'Newington', 'Wentworth Point',
    'Wolli Creek', 'Arncliffe', 'Tempe', 'Sydenham', 'St Peters',
    'Erskineville', 'Waterloo', 'Zetland', 'Rosebery', 'Eastlakes',
    'Daceyville', 'Kingsford', 'Matraville', 'Chifley', 'Phillip Bay',
    'Brookvale', 'Freshwater', 'Curl Curl', 'North Curl Curl',
    'Warriewood', 'Mona Vale', 'Newport', 'Avalon Beach', 'Palm Beach',
    'Kirrawee', 'Gymea', 'Miranda', 'Sylvania', 'Taren Point',
    'Beverley Park', 'Carlton', 'Ramsgate', 'Brighton-Le-Sands',
    'Mortdale', 'Penshurst', 'Oatley', 'Lugarno', 'Peakhurst',
    'Castle Cove', 'Middle Cove', 'Roseville', 'East Lindfield',
    'Macquarie Park', 'North Ryde', 'Eastwood', 'Denistone',
    'West Ryde', 'Meadowbank', 'Gladesville', 'Hunters Hill',
    'Woolwich', 'Longueville', 'Greenwich', 'Riverview',
    'Naremburn', 'Cammeray', 'Cremorne', 'Cremorne Point',
    'Crows Nest', 'Wollstonecraft', 'St Leonards',
    'Kellyville Ridge', 'Beaumont Hills', 'The Hills Shire',
    'New South Wales',  # catches "New South Wales" as city name (road photos)
}

# Rename map for display
RENAME_MAP = {
    'Chessy': 'Disneyland Paris',
    'Bailly-Romainvilliers': 'Disneyland Paris',
    'Villeneuve-le-Comte': 'Disneyland Paris',
    'Bay Lake': 'Walt Disney World',
    'Amphoe Bang Phli': 'Bangkok',
    'Bang Phli District': 'Bangkok',
    'Chek Lap Kok': 'Hong Kong',
    'Hounslow': 'Heathrow Airport',
    'Stockholm-Arlanda': 'Stockholm',
    'Tremblay-en-France': 'Paris CDG Airport',
    'Deira Islands': 'Dubai',
    'Pukaki Ward': 'Mt Cook',
    'Queenstown-Wakatipu Ward': 'Queenstown',
    'Vantaa': 'Helsinki',
    'Romford': 'London',
    'Fujiyoshida': 'Mt Fuji',
}

# Tokyo wards to merge into Tokyo
TOKYO_MERGE = {
    'Shibuya', 'Shinjuku', 'Taito', 'Chiyoda', 'Minato', 'Chuo',
    'Meguro', 'Shinagawa', 'Ota', 'Setagaya', 'Suginami', 'Nakano',
    'Toshima', 'Kita', 'Itabashi', 'Nerima', 'Bunkyo', 'Sumida',
    'Koto', 'Edogawa', 'Arakawa', 'Adachi', 'Katsushika',
}


def extract_postal(blob):
    """Extract _city, _subLocality, _state, _ISOCountryCode from postalAddress."""
    try:
        data = plistlib.loads(blob)
        objects = data.get('$objects', [])
        
        def resolve(uid):
            if uid is None:
                return None
            idx = uid.data if hasattr(uid, 'data') else (int(uid) if isinstance(uid, (int, float)) else None)
            if idx is not None and 0 < idx < len(objects):
                val = objects[idx]
                return val if isinstance(val, str) and val != '$null' else None
            return None
        
        # Find the CNPostalAddress dict
        for obj in objects:
            if isinstance(obj, dict) and '_city' in obj and '_ISOCountryCode' in obj:
                return {
                    'city': resolve(obj.get('_city')),
                    'subLocality': resolve(obj.get('_subLocality')),
                    'state': resolve(obj.get('_state')),
                    'country_code': resolve(obj.get('_ISOCountryCode')),
                    'country_name': resolve(obj.get('_country')),
                }
        
        # Fallback: get countryCode from root
        root = objects[1] if len(objects) > 1 else {}
        if isinstance(root, dict):
            cc = resolve(root.get('countryCode'))
            if cc:
                return {'city': None, 'subLocality': None, 'state': None, 'country_code': cc, 'country_name': None}
        
        return None
    except Exception:
        return None


def main():
    conn = sqlite3.connect(DB)
    
    # ─── PHASE 1: Extract GPS photos ───
    print("Phase 1: Extracting with Apple's reverse geocoding...", file=sys.stderr)
    
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
    
    groups = defaultdict(lambda: {
        'count': 0, 'lats': [], 'lons': [], 'dates': [],
        'country_code': None, 'state': None, 'subLocality': None,
    })
    
    processed = 0
    no_city = 0
    
    for lat, lon, date_val, blob in cur:
        postal = extract_postal(blob)
        if not postal or not postal.get('country_code'):
            continue
        
        cc = postal['country_code']
        city = postal.get('city')
        sub = postal.get('subLocality')
        
        if not city:
            no_city += 1
            continue
        
        # Merge Sydney suburbs
        display_name = city
        if cc == 'AU' and city in SYDNEY_MERGE:
            display_name = 'Sydney'
        
        # Merge Tokyo wards
        if cc == 'JP' and city in TOKYO_MERGE:
            display_name = 'Tokyo'
        
        # Apply renames
        if display_name in RENAME_MAP:
            display_name = RENAME_MAP[display_name]
        
        # For non-AU: also use subLocality for granularity in big cities
        # e.g., "Shinjuku" in Tokyo, "Monti" in Rome, "4th Arr." in Paris
        # But group by city for the main grouping
        
        key = f"{display_name}|{cc}"
        g = groups[key]
        g['count'] += 1
        g['lats'].append(lat)
        g['lons'].append(lon)
        if date_val:
            g['dates'].append(date_val)
        g['country_code'] = cc
        g['state'] = postal.get('state') or g['state']
        processed += 1
    
    print(f"Processed {processed:,} photos ({no_city} had no city)", file=sys.stderr)
    
    # ─── PHASE 2: Date proximity ───
    print("Phase 2: Date proximity for no-GPS photos...", file=sys.stderr)
    
    gps_timeline = list(conn.execute("""
        SELECT ZDATECREATED, ZLATITUDE, ZLONGITUDE FROM ZASSET
        WHERE ZLATITUDE > -85 AND ZLATITUDE < 85 
          AND ZLONGITUDE > -179 AND ZLONGITUDE < 179
          AND ZTRASHEDSTATE = 0
        ORDER BY ZDATECREATED
    """))
    gps_dates = [t[0] for t in gps_timeline]
    
    no_gps = list(conn.execute("""
        SELECT ZDATECREATED FROM ZASSET
        WHERE (ZLATITUDE = 0 OR ZLATITUDE = -180 OR ZLATITUDE IS NULL)
          AND ZTRASHEDSTATE = 0 AND ZDATECREATED IS NOT NULL
        ORDER BY ZDATECREATED
    """))
    
    inferred = 0
    for (date_val,) in no_gps:
        idx = bisect.bisect_left(gps_dates, date_val)
        best = float('inf')
        for i in [idx - 1, idx]:
            if 0 <= i < len(gps_timeline):
                d = abs(gps_timeline[i][0] - date_val)
                if d < best:
                    best = d
        if best <= 7200:
            inferred += 1
    
    print(f"Inferred {inferred:,} photos", file=sys.stderr)
    
    # ─── PHASE 2.5: Manual locations (vision-identified no-GPS photos) ───
    manual_file = os.path.join(os.path.dirname(__file__), 'manual-locations.json')
    if os.path.exists(manual_file):
        print("Phase 2.5: Adding manually identified locations...", file=sys.stderr)
        with open(manual_file) as f:
            manual = json.load(f)
        
        for entry in manual.get('entries', []):
            loc_name = entry['location']
            cc = entry['country_code']
            
            # Count photos for these dates
            date_clauses = " OR ".join(
                f"date(datetime(ZDATECREATED + 978307200, 'unixepoch')) = '{d}'" 
                for d in entry['dates']
            )
            count_row = conn.execute(f"""
                SELECT COUNT(*) FROM ZASSET 
                WHERE ({date_clauses})
                  AND ZTRASHEDSTATE = 0
                  AND (ZLATITUDE = 0 OR ZLATITUDE = -180 OR ZLATITUDE IS NULL)
            """).fetchone()
            photo_count = count_row[0] if count_row else 0
            
            if photo_count == 0:
                continue
            
            # Also get the date range in CoreData timestamp format
            date_row = conn.execute(f"""
                SELECT MIN(ZDATECREATED), MAX(ZDATECREATED) FROM ZASSET 
                WHERE ({date_clauses})
                  AND ZTRASHEDSTATE = 0
                  AND (ZLATITUDE = 0 OR ZLATITUDE = -180 OR ZLATITUDE IS NULL)
            """).fetchone()
            
            key = f"{loc_name}|{cc}"
            if key not in groups:
                groups[key] = {
                    'count': 0, 'lats': [], 'lons': [], 'dates': [],
                    'country_code': cc, 'state': entry.get('continent', ''), 'subLocality': None,
                }
            g = groups[key]
            g['count'] += photo_count
            g['lats'].append(entry['lat'])
            g['lons'].append(entry['lon'])
            if date_row and date_row[0]:
                g['dates'].append(date_row[0])
            if date_row and date_row[1]:
                g['dates'].append(date_row[1])
            g['country_code'] = cc
            
            print(f"  + {entry['flag']} {loc_name}: {photo_count} photos ({entry['note']})", file=sys.stderr)
    
    # ─── PHASE 3: Build output ───
    CORE_EPOCH = 978307200
    MIN_PHOTOS = 10
    
    cities = []
    for key, g in groups.items():
        if g['count'] < MIN_PHOTOS:
            continue
        
        name, cc = key.split('|', 1)
        avg_lat = sum(g['lats']) / len(g['lats'])
        avg_lon = sum(g['lons']) / len(g['lons'])
        dates = sorted(g['dates'])
        
        first = datetime.utcfromtimestamp(dates[0] + CORE_EPOCH).strftime('%Y-%m-%d') if dates else ''
        last = datetime.utcfromtimestamp(dates[-1] + CORE_EPOCH).strftime('%Y-%m-%d') if dates else ''
        
        country = COUNTRY_NAME.get(cc, cc)
        continent = CONTINENT_MAP.get(cc, 'Unknown')
        flag = FLAG_MAP.get(cc, '🏳️')
        
        cities.append({
            'name': name,
            'country': country,
            'continent': continent,
            'lat': round(avg_lat, 4),
            'lon': round(avg_lon, 4),
            'count': g['count'],
            'firstDate': first,
            'lastDate': last,
            'flag': flag,
            'region': g.get('state', ''),
            'isHome': name == 'Sydney' and cc == 'AU',
        })
    
    cities.sort(key=lambda c: c['count'], reverse=True)
    total = sum(c['count'] for c in cities)
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"FINAL: {len(cities)} locations across {len(set(c['country'] for c in cities))} countries", file=sys.stderr)
    print(f"Total: {total:,} GPS photos + {inferred:,} proximity-inferred", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    
    # Summary by country
    by_country = defaultdict(list)
    for c in cities:
        by_country[c['country']].append(c)
    
    for country in sorted(by_country, key=lambda x: sum(c['count'] for c in by_country[x]), reverse=True):
        locs = by_country[country]
        t = sum(c['count'] for c in locs)
        print(f"\n{locs[0]['flag']} {country} — {len(locs)} locations, {t:,} photos", file=sys.stderr)
        for c in sorted(locs, key=lambda x: x['count'], reverse=True)[:8]:
            print(f"  {c['name']:30s} {c['count']:>7,d}  {c['firstDate']} → {c['lastDate']}", file=sys.stderr)
        if len(locs) > 8:
            print(f"  ... +{len(locs)-8} more", file=sys.stderr)
    
    # Write JS
    js = f"""// Travel Radar — Apple Photos GPS Intelligence
// {len(cities)} locations, {total:,} photos (+{inferred:,} inferred)
// Generated: {datetime.now().isoformat()[:19]}

export const travelData = {{
  totalPhotosWithGPS: {total},
  inferredFromProximity: {inferred},
  cities: {json.dumps(cities, indent=2, ensure_ascii=False)}
}};

export function getStats(cities) {{
  const countries = new Set(cities.map(c => c.country));
  const continents = new Set(cities.map(c => c.continent));
  const totalPhotos = cities.reduce((s, c) => s + c.count, 0);
  return {{ countries: countries.size, cities: cities.length, continents: continents.size, totalPhotos, countryList: [...countries].sort() }};
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
    
    with open(OUTPUT, 'w') as f:
        f.write(js)
    print(f"\n✅ Written to {OUTPUT}", file=sys.stderr)
    conn.close()

if __name__ == '__main__':
    main()
