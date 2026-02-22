import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Globe from 'globe.gl';
import { travelData, getStats, getYearRange } from './data/locations';
import './index.css';

// ─── CONSTANTS ────────────────────────────
const PINK = '#ff3399';
const CYAN = '#44ccbb';
const PURPLE = '#7744aa';
const BG = '#0a0d14';

function App() {
  const globeRef = useRef(null);
  const globeInstance = useRef(null);
  const [selectedCity, setSelectedCity] = useState(null);
  const [yearFilter, setYearFilter] = useState(null);
  const [hoveredCity, setHoveredCity] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playYear, setPlayYear] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [continentFilter, setContinentFilter] = useState(null);
  const playRef = useRef(null);
  const [time, setTime] = useState(new Date());
  const [showPaths, setShowPaths] = useState(true);

  const { min: minYear, max: maxYear } = useMemo(() => getYearRange(travelData.cities), []);

  // Filter cities
  const filteredCities = useMemo(() => {
    let cities = travelData.cities;
    const activeYear = isPlaying ? playYear : yearFilter;
    if (activeYear) {
      cities = cities.filter(c => {
        const s = parseInt(c.firstDate.slice(0, 4));
        const e = parseInt(c.lastDate.slice(0, 4));
        return s <= activeYear && e >= activeYear;
      });
    }
    if (continentFilter) {
      cities = cities.filter(c => c.continent === continentFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      cities = cities.filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.country.toLowerCase().includes(q) ||
        c.continent.toLowerCase().includes(q)
      );
    }
    return cities;
  }, [yearFilter, continentFilter, searchQuery, isPlaying, playYear]);

  const stats = useMemo(() => getStats(filteredCities), [filteredCities]);

  // Flight paths between cities (chronological order by first visit)
  const flightPaths = useMemo(() => {
    if (!showPaths) return [];
    const sorted = [...filteredCities]
      .filter(c => !c.isHome)
      .sort((a, b) => a.firstDate.localeCompare(b.firstDate));

    const paths = [];
    // Connect from home to first, then city to city
    const home = travelData.cities.find(c => c.isHome);
    if (home && sorted.length > 0) {
      // Start from home
      let prev = home;
      for (const city of sorted) {
        paths.push({
          startLat: prev.lat,
          startLng: prev.lon,
          endLat: city.lat,
          endLng: city.lon,
          color: [CYAN, PINK],
        });
        prev = city;
      }
    }
    return paths;
  }, [filteredCities, showPaths]);

  // Clock
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Play animation
  const togglePlay = useCallback(() => {
    if (isPlaying) {
      setIsPlaying(false);
      clearInterval(playRef.current);
      setPlayYear(null);
    } else {
      setIsPlaying(true);
      setPlayYear(minYear);
      playRef.current = setInterval(() => {
        setPlayYear(prev => {
          if (prev >= maxYear) {
            setIsPlaying(false);
            clearInterval(playRef.current);
            return null;
          }
          return prev + 1;
        });
      }, 1500);
    }
  }, [isPlaying, minYear, maxYear]);

  // Initialize globe
  useEffect(() => {
    if (!globeRef.current) return;

    const globe = Globe()(globeRef.current)
      .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
      .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
      .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
      .showAtmosphere(true)
      .atmosphereColor(PINK)
      .atmosphereAltitude(0.15)
      .width(window.innerWidth)
      .height(window.innerHeight)
      // Points (cities)
      .pointsData([])
      .pointLat('lat')
      .pointLng('lon')
      .pointAltitude(d => Math.min(d.count / 5000, 0.5))
      .pointRadius(d => Math.max(0.15, Math.min(Math.log10(d.count) * 0.25, 1.2)))
      .pointColor(d => d.isHome ? CYAN : PINK)
      .pointResolution(12)
      .onPointClick(d => setSelectedCity(d))
      .onPointHover(d => setHoveredCity(d))
      // Labels
      .labelsData([])
      .labelLat('lat')
      .labelLng('lon')
      .labelText(d => d.name.toUpperCase())
      .labelSize(d => Math.max(0.3, Math.min(Math.log10(d.count) * 0.2, 0.8)))
      .labelDotRadius(0)
      .labelColor(() => 'rgba(255, 255, 255, 0.7)')
      .labelResolution(2)
      .labelAltitude(d => Math.min(d.count / 5000, 0.5) + 0.01)
      // Arcs (flight paths)
      .arcsData([])
      .arcStartLat('startLat')
      .arcStartLng('startLng')
      .arcEndLat('endLat')
      .arcEndLng('endLng')
      .arcColor('color')
      .arcAltitudeAutoScale(0.4)
      .arcStroke(0.4)
      .arcDashLength(0.6)
      .arcDashGap(0.3)
      .arcDashAnimateTime(2000)
      // Rings (pulse effect)
      .ringsData([])
      .ringLat('lat')
      .ringLng('lon')
      .ringMaxRadius(d => Math.max(1, Math.log10(d.count) * 0.8))
      .ringPropagationSpeed(1.5)
      .ringRepeatPeriod(1200)
      .ringColor(() => t => `rgba(255, 51, 153, ${1 - t})`);

    // Set initial view to show Australia/Asia
    globe.pointOfView({ lat: -20, lng: 140, altitude: 2.5 }, 0);

    // Auto-rotate
    globe.controls().autoRotate = true;
    globe.controls().autoRotateSpeed = 0.3;
    globe.controls().enableDamping = true;

    globeInstance.current = globe;

    const handleResize = () => {
      globe.width(window.innerWidth).height(window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // Update globe data when filters change
  useEffect(() => {
    if (!globeInstance.current) return;
    const globe = globeInstance.current;

    // Only show labels for cities with significant count
    const labelCities = filteredCities.filter(c => c.count > 100);

    globe
      .pointsData(filteredCities)
      .labelsData(labelCities)
      .arcsData(flightPaths)
      .ringsData(filteredCities.filter(c => c.count > 200));
  }, [filteredCities, flightPaths]);

  // Fly to selected city
  useEffect(() => {
    if (selectedCity && globeInstance.current) {
      globeInstance.current.pointOfView(
        { lat: selectedCity.lat, lng: selectedCity.lon, altitude: 1.5 },
        1000
      );
    }
  }, [selectedCity]);

  const formatDate = (d) => {
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}, ${d.getFullYear()}`;
  };
  const formatTime = (d) =>
    `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;

  const continents = [...new Set(travelData.cities.map(c => c.continent))].sort();

  return (
    <div className="relative w-full h-full">
      {/* Globe */}
      <div ref={globeRef} className="globe-container absolute inset-0" />

      {/* ─── HEADER ─── */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-3 z-10">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-[#ff3399]" />
          <span className="text-xs tracking-[0.2em] text-gray-400 uppercase">Travel Radar</span>
          <span className="text-xs tracking-[0.1em] text-gray-600">•</span>
          <span className="text-xs tracking-[0.1em] text-gray-500 uppercase">Sector M-AU</span>
        </div>
        <div className="text-center">
          <h1 className="text-lg tracking-[0.3em] text-white font-bold uppercase">Travel Radar</h1>
          <p className="text-[10px] tracking-[0.25em] text-gray-500 uppercase">GPS Photo Intelligence System v1.0</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-ghost text-xs" onClick={() => { setYearFilter(null); setContinentFilter(null); setSearchQuery(''); setSelectedCity(null); }}>
            Reset
          </button>
          <button className="btn-primary text-xs" onClick={togglePlay}>
            {isPlaying ? '■ Stop' : '▶ Play'}
          </button>
        </div>
      </div>

      {/* ─── DATA PANEL (top-left) ─── */}
      <div className="panel absolute top-16 left-4 p-4 z-10 w-64">
        <div className="space-y-2 text-xs uppercase tracking-wider">
          <div className="flex justify-between">
            <span className="text-gray-500">Time</span>
            <span className="text-white">{formatTime(time)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Date</span>
            <span className="text-white">{formatDate(time)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Tracked</span>
            <span className="stat-value">{stats.cities} Locations</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Countries</span>
            <span className="stat-value">{stats.countries}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Continents</span>
            <span className="stat-value">{stats.continents}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Photos</span>
            <span className="stat-value">{stats.totalPhotos.toLocaleString()}</span>
          </div>
          {(isPlaying && playYear) && (
            <div className="flex justify-between border-t border-[rgba(255,51,153,0.2)] pt-2 mt-2">
              <span className="text-gray-500">Year</span>
              <span className="stat-value text-lg">{playYear}</span>
            </div>
          )}
        </div>
      </div>

      {/* ─── SEARCH + FILTERS (top-right) ─── */}
      <div className="absolute top-16 right-4 z-10 w-64 space-y-2">
        <div className="panel p-3">
          <input
            type="text"
            placeholder="SEARCH..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent border border-[rgba(255,51,153,0.3)] text-white text-xs tracking-wider px-3 py-2 uppercase outline-none focus:border-[#ff3399] placeholder:text-gray-600 font-mono"
          />
        </div>
        <div className="panel p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Continent</p>
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => setContinentFilter(null)}
              className={`text-[10px] px-2 py-1 uppercase tracking-wider border ${!continentFilter ? 'border-[#ff3399] text-[#ff3399]' : 'border-gray-700 text-gray-500 hover:border-gray-500'}`}
            >
              All
            </button>
            {continents.map(c => (
              <button
                key={c}
                onClick={() => setContinentFilter(continentFilter === c ? null : c)}
                className={`text-[10px] px-2 py-1 uppercase tracking-wider border ${continentFilter === c ? 'border-[#ff3399] text-[#ff3399]' : 'border-gray-700 text-gray-500 hover:border-gray-500'}`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="panel p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Flight Paths</p>
            <button
              onClick={() => setShowPaths(!showPaths)}
              className={`text-[10px] px-2 py-1 uppercase tracking-wider border ${showPaths ? 'border-[#44ccbb] text-[#44ccbb]' : 'border-gray-700 text-gray-500'}`}
            >
              {showPaths ? 'On' : 'Off'}
            </button>
          </div>
        </div>
      </div>

      {/* ─── YEAR SLIDER (bottom) ─── */}
      <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-10 w-[60%]">
        <div className="panel p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Timeline</span>
            <span className="text-[10px] text-gray-400 uppercase tracking-wider">
              {yearFilter ? yearFilter : 'All Years'}
            </span>
          </div>
          <input
            type="range"
            min={minYear}
            max={maxYear}
            value={yearFilter || maxYear}
            onChange={(e) => setYearFilter(parseInt(e.target.value))}
            className="w-full h-1 appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(90deg, #44ccbb 0%, #ff3399 ${((yearFilter || maxYear) - minYear) / (maxYear - minYear) * 100}%, #333 ${((yearFilter || maxYear) - minYear) / (maxYear - minYear) * 100}%)`,
              borderRadius: '2px',
            }}
          />
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-gray-600">{minYear}</span>
            <button
              onClick={() => setYearFilter(null)}
              className="text-[10px] text-gray-600 hover:text-[#ff3399] uppercase tracking-wider"
            >
              Clear
            </button>
            <span className="text-[10px] text-gray-600">{maxYear}</span>
          </div>
        </div>
      </div>

      {/* ─── SELECTED CITY DETAIL ─── */}
      {selectedCity && (
        <div className="panel absolute bottom-36 left-4 z-10 w-72 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                {selectedCity.flag} {selectedCity.name}
              </h3>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">
                {selectedCity.country} • {selectedCity.continent}
              </p>
            </div>
            <button
              onClick={() => setSelectedCity(null)}
              className="text-gray-600 hover:text-white text-xs"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1.5 text-xs uppercase tracking-wider">
            <div className="flex justify-between">
              <span className="text-gray-500">Photos</span>
              <span className="stat-value">{selectedCity.count.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">First Visit</span>
              <span className="text-white">{selectedCity.firstDate}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Last Visit</span>
              <span className="text-white">{selectedCity.lastDate}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Coordinates</span>
              <span className="text-[#44ccbb]">{selectedCity.lat.toFixed(2)}° {selectedCity.lon.toFixed(2)}°</span>
            </div>
          </div>
        </div>
      )}

      {/* ─── HOVER TOOLTIP ─── */}
      {hoveredCity && !selectedCity && (
        <div className="panel absolute top-1/2 left-1/2 z-10 p-3 pointer-events-none transform -translate-x-1/2 -translate-y-full -mt-4">
          <p className="text-xs font-bold text-white uppercase tracking-wider">
            {hoveredCity.flag} {hoveredCity.name}
          </p>
          <p className="text-[10px] text-gray-400">
            {hoveredCity.count.toLocaleString()} photos • {hoveredCity.country}
          </p>
        </div>
      )}

      {/* ─── CITY LIST (left sidebar, scrollable) ─── */}
      <div className="panel absolute top-52 left-4 bottom-20 z-10 w-64 overflow-y-auto">
        <div className="p-3 border-b border-[rgba(255,51,153,0.2)]">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
            Locations • {filteredCities.length}
          </p>
        </div>
        <div className="divide-y divide-[rgba(255,51,153,0.1)]">
          {filteredCities
            .sort((a, b) => b.count - a.count)
            .map(city => (
              <button
                key={city.name}
                onClick={() => setSelectedCity(city)}
                className={`w-full text-left px-3 py-2 hover:bg-[rgba(255,51,153,0.08)] transition-colors ${selectedCity?.name === city.name ? 'bg-[rgba(255,51,153,0.15)]' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-white uppercase tracking-wider truncate">
                    {city.flag} {city.name}
                  </span>
                  <span className="text-[10px] stat-value ml-2 shrink-0">
                    {city.count > 1000 ? `${(city.count / 1000).toFixed(1)}k` : city.count}
                  </span>
                </div>
                <p className="text-[9px] text-gray-600 uppercase tracking-wider">
                  {city.country}
                </p>
              </button>
            ))}
        </div>
      </div>

      {/* ─── STATUS BAR (bottom) ─── */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-6 py-2 z-10 bg-[rgba(10,13,20,0.9)] border-t border-[rgba(255,51,153,0.15)]">
        <div className="flex items-center gap-4 text-[10px] tracking-wider uppercase">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            System Online
          </span>
          <span className="text-gray-600">|</span>
          <span className="text-gray-500">{formatTime(time)} AEST</span>
          <span className="text-gray-600">|</span>
          <span className="text-gray-500">
            {travelData.totalPhotosWithGPS.toLocaleString()} GPS Points
          </span>
        </div>
        <div className="text-[10px] text-gray-600 tracking-wider uppercase">
          Drag Rotate • Scroll Zoom • Click Select
        </div>
      </div>
    </div>
  );
}

export default App;
