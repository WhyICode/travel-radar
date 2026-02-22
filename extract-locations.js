const { execSync } = require('child_process');
const path = require('path');

const DB = path.join(process.env.HOME, 'Pictures/Photos Library.photoslibrary/database/Photos.sqlite');

// Get all location clusters (rounded to 0.1 degree ~ 11km)
const raw = execSync(`sqlite3 "${DB}" "
SELECT 
  round(ZLATITUDE, 1) as lat,
  round(ZLONGITUDE, 1) as lon,
  COUNT(*) as count,
  MIN(datetime(ZDATECREATED + 978307200, 'unixepoch')) as first_date,
  MAX(datetime(ZDATECREATED + 978307200, 'unixepoch')) as last_date
FROM ZASSET
WHERE ZLATITUDE > -85 AND ZLATITUDE < 85 
  AND ZLONGITUDE > -179 AND ZLONGITUDE < 179
  AND ZTRASHEDSTATE = 0
GROUP BY lat, lon
HAVING count >= 5
ORDER BY count DESC;
"`, { encoding: 'utf-8' });

const locations = raw.trim().split('\n').map(line => {
  const [lat, lon, count, firstDate, lastDate] = line.split('|');
  return { lat: parseFloat(lat), lon: parseFloat(lon), count: parseInt(count), firstDate, lastDate };
});

// Known city mapping (rough reverse geocoding by coordinate ranges)
const cities = [
  { name: 'Sydney', country: 'Australia', lat: -33.87, lon: 151.21, radius: 0.8 },
  { name: 'Kellyville', country: 'Australia', lat: -33.71, lon: 150.95, radius: 0.15 },
  { name: 'Melbourne', country: 'Australia', lat: -37.81, lon: 144.96, radius: 0.5 },
  { name: 'Canberra', country: 'Australia', lat: -35.28, lon: 149.13, radius: 0.3 },
  { name: 'Darwin', country: 'Australia', lat: -12.46, lon: 130.84, radius: 0.3 },
  { name: 'Paris', country: 'France', lat: 48.86, lon: 2.35, radius: 0.5 },
  { name: 'Rome', country: 'Italy', lat: 41.90, lon: 12.50, radius: 0.3 },
  { name: 'Florence', country: 'Italy', lat: 43.77, lon: 11.25, radius: 0.2 },
  { name: 'Venice', country: 'Italy', lat: 45.44, lon: 12.34, radius: 0.2 },
  { name: 'London', country: 'UK', lat: 51.51, lon: -0.13, radius: 0.4 },
  { name: 'Stockholm', country: 'Sweden', lat: 59.33, lon: 18.07, radius: 0.3 },
  { name: 'Gibraltar', country: 'Spain', lat: 36.14, lon: -5.35, radius: 0.2 },
  { name: 'Marbella', country: 'Spain', lat: 36.51, lon: -4.88, radius: 0.3 },
  { name: 'Tokyo', country: 'Japan', lat: 35.68, lon: 139.69, radius: 0.5 },
  { name: 'Kyoto', country: 'Japan', lat: 35.01, lon: 135.77, radius: 0.3 },
  { name: 'Athens', country: 'Greece', lat: 37.98, lon: 23.73, radius: 0.3 },
  { name: 'Chamonix', country: 'France', lat: 45.92, lon: 6.87, radius: 0.3 },
  { name: 'Queenstown', country: 'New Zealand', lat: -45.03, lon: 168.66, radius: 0.3 },
  { name: 'Hong Kong', country: 'Hong Kong', lat: 22.32, lon: 114.17, radius: 0.3 },
  { name: 'Dubai', country: 'UAE', lat: 25.20, lon: 55.27, radius: 0.4 },
  { name: 'New York', country: 'USA', lat: 40.71, lon: -74.01, radius: 0.4 },
  { name: 'Amsterdam', country: 'Netherlands', lat: 52.37, lon: 4.90, radius: 0.3 },
  { name: 'Newcastle', country: 'Australia', lat: -32.93, lon: 151.78, radius: 0.5 },
  { name: 'Gold Coast', country: 'Australia', lat: -28.02, lon: 153.43, radius: 0.4 },
  { name: 'Byron Bay', country: 'Australia', lat: -28.64, lon: 153.61, radius: 0.3 },
  { name: 'Coffs Harbour', country: 'Australia', lat: -30.30, lon: 153.11, radius: 0.3 },
  { name: 'Port Stephens', country: 'Australia', lat: -32.72, lon: 152.17, radius: 0.4 },
  { name: 'Forster', country: 'Australia', lat: -32.18, lon: 152.52, radius: 0.3 },
  { name: 'Disneyland Paris', country: 'France', lat: 48.87, lon: 2.78, radius: 0.15 },
  { name: 'Albury-Wodonga', country: 'Australia', lat: -36.08, lon: 146.92, radius: 0.3 },
  { name: 'Pisa', country: 'Italy', lat: 43.72, lon: 10.40, radius: 0.2 },
];

// Match locations to cities
const cityData = {};
const unmatched = [];

for (const loc of locations) {
  let matched = false;
  for (const city of cities) {
    const dist = Math.sqrt(Math.pow(loc.lat - city.lat, 2) + Math.pow(loc.lon - city.lon, 2));
    if (dist <= city.radius) {
      if (!cityData[city.name]) {
        cityData[city.name] = { 
          name: city.name, country: city.country, 
          lat: city.lat, lon: city.lon, 
          count: 0, firstDate: loc.firstDate, lastDate: loc.lastDate 
        };
      }
      cityData[city.name].count += loc.count;
      if (loc.firstDate < cityData[city.name].firstDate) cityData[city.name].firstDate = loc.firstDate;
      if (loc.lastDate > cityData[city.name].lastDate) cityData[city.name].lastDate = loc.lastDate;
      matched = true;
      break;
    }
  }
  if (!matched && loc.count > 20) {
    unmatched.push(loc);
  }
}

const result = Object.values(cityData).sort((a, b) => b.count - a.count);

console.log(JSON.stringify({ cities: result, unmatched, totalPhotosWithGPS: locations.reduce((s,l) => s+l.count, 0) }, null, 2));
