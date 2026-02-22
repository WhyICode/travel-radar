# 🛰️ Travel Radar

GPS-powered travel dashboard built from Apple Photos metadata. Dark tactical UI inspired by orbital defense grid aesthetics.

## Features

- 🌍 Interactive 3D globe with night Earth texture
- 📍 56+ locations across 21 countries, 5 continents
- ✈️ Animated flight path arcs between cities
- 📅 Year timeline slider with playback animation
- 🔍 Search & filter by continent, year, text
- 📊 Real-time stats (countries, photos, continents)
- 📸 124K+ GPS-tagged photos from Apple Photos

## Tech Stack

- **Frontend:** React + Vite
- **Globe:** globe.gl (Three.js)
- **Styling:** Tailwind CSS v4
- **Data:** Apple Photos SQLite (EXIF GPS extraction)
- **Deployment:** Docker + nginx

## Quick Start

```bash
# Development
cd app && npm install && npm run dev

# Docker
docker compose up -d
# → http://localhost:3210
```

## Data Extraction

The `extract-locations.js` script reads GPS coordinates from Apple Photos' SQLite database, clusters them into cities, and outputs the `src/data/locations.js` file.

```bash
node extract-locations.js
```

## Project Structure

```
travel-radar/
├── app/                    # Vite React app
│   ├── src/
│   │   ├── data/locations.js  # GPS data (auto-generated)
│   │   ├── App.jsx            # Main globe component
│   │   └── index.css          # Tailwind + custom styles
│   └── package.json
├── extract-locations.js    # Apple Photos GPS extractor
├── Dockerfile             # Multi-stage build
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## Author

Built by Goose 🐦‍⬛ for Maverick 🫡
