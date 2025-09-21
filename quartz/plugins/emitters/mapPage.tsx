import { QuartzEmitterPlugin } from "../types"
import { FilePath, FullSlug } from "../../util/path"
import { write } from "./helpers"

export const MapPage: QuartzEmitterPlugin = () => {
  return {
    name: "MapPage",
    getQuartzComponents() {
      return []
    },
    async emit(ctx, content, resources): Promise<FilePath[]> {
      const fps: FilePath[] = []
      const allFiles = content.map((c) => c[1].data)
      
      // Extract locations with more metadata
      const locationsData = allFiles
        .filter(f => f.frontmatter?.position || f.frontmatter?.coordinates || f.frontmatter?.location)
        .map(f => {
          // Handle position field (comma-separated string)
          let coords = null
          if (f.frontmatter?.position) {
            const parts = String(f.frontmatter.position).split(",").map(s => s.trim())
            if (parts.length === 2) {
              const lat = Number(parts[0])
              const lon = Number(parts[1])
              if (!isNaN(lat) && !isNaN(lon)) {
                coords = [lat, lon]
              }
            }
          } else if (f.frontmatter?.coordinates) {
            coords = f.frontmatter.coordinates
          }
          
          // Extract location from Topics or Location field
          let location = f.frontmatter?.location || f.frontmatter?.Location || null
          if (!location && f.frontmatter?.Topics && Array.isArray(f.frontmatter.Topics)) {
            const locationTopics = f.frontmatter.Topics.filter((topic: string) => 
              !['OTC', 'CryptoToCash', 'P2P'].includes(topic)
            )
            if (locationTopics.length > 0) {
              location = locationTopics.join(", ")
            }
          }
          
          return {
            slug: f.slug || "",
            title: f.frontmatter?.title || f.slug || "Untitled",
            location: location,
            coordinates: coords,
            tags: f.frontmatter?.tags || [],
            date: f.frontmatter?.date || f.frontmatter?.created || f.frontmatter?.["Intelligence Cut Off Date"] || null,
            description: f.description || f.frontmatter?.description || "",
            classification: f.frontmatter?.Classification || null,
            reportType: f.frontmatter?.["Report Type"] || null,
            serviceType: f.frontmatter?.["Service Type"] || null,
            topics: f.frontmatter?.Topics || [],
          }
        })
      
      // Extract all unique tags and topics for filter dropdown
      const allTags = [...new Set(locationsData.flatMap(loc => loc.tags))].sort()
      const allTopics = [...new Set(locationsData.flatMap(loc => loc.topics))].sort()
      
      // Predefined filter sets for common queries
      const filterPresets = [
        { name: "Hong Kong OTC", tags: ["P2PDesk"], topics: ["Hong Kong"] },
        { name: "Dubai OTC", tags: ["P2PDesk"], topics: ["Dubai", "UAE"] },
        { name: "All P2P Desks", tags: ["P2PDesk"], topics: [] },
        { name: "Highly Sensitive", classification: "HIGHLY SENSITIVE", tags: [], topics: [] },
        { name: "Public", classification: "PUBLIC", tags: [], topics: [] }
      ]
      
      // Create an enhanced HTML page with filtering and radius search
      const mapHtml = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Intelligence Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      background: #1a1a1a;
      color: #e0e0e0;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    
    .header {
      background: #2a2a2a;
      padding: 15px 20px;
      border-bottom: 1px solid #3a3a3a;
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    
    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    
    h1 {
      color: #e0e0e0;
      font-size: 22px;
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 600;
    }
    
    .classification-badge {
      background: #8b0000;
      color: white;
      padding: 3px 8px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: bold;
      letter-spacing: 0.5px;
    }
    
    .back-link {
      color: #4a9eff;
      text-decoration: none;
      font-size: 14px;
    }
    
    .back-link:hover {
      text-decoration: underline;
    }
    
    .stats {
      color: #999;
      font-size: 13px;
    }
    
    .filters {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    
    .filter-group {
      display: flex;
      flex-direction: column;
      gap: 5px;
      flex: 1;
      min-width: 180px;
    }
    
    .filter-label {
      font-size: 11px;
      color: #999;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    input[type="text"], input[type="number"], select {
      padding: 8px 12px;
      border: 1px solid #3a3a3a;
      border-radius: 4px;
      font-size: 13px;
      background: #1a1a1a;
      color: #e0e0e0;
      transition: border-color 0.2s;
    }
    
    input[type="text"]:focus, input[type="number"]:focus, select:focus {
      outline: none;
      border-color: #4a9eff;
    }
    
    .preset-filters {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    
    .preset-btn {
      padding: 6px 12px;
      background: #3a3a3a;
      border: 1px solid #4a4a4a;
      border-radius: 4px;
      color: #e0e0e0;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s;
    }
    
    .preset-btn:hover {
      background: #4a4a4a;
    }
    
    .preset-btn.active {
      background: #4a9eff;
      border-color: #4a9eff;
      color: white;
    }
    
    .tag-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      max-height: 60px;
      overflow-y: auto;
      padding: 5px 0;
    }
    
    .tag-filter, .topic-filter {
      padding: 4px 10px;
      background: #3a3a3a;
      border: 1px solid #4a4a4a;
      border-radius: 15px;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      color: #e0e0e0;
    }
    
    .tag-filter:hover, .topic-filter:hover {
      background: #4a4a4a;
    }
    
    .tag-filter.active, .topic-filter.active {
      background: #4a9eff;
      color: white;
      border-color: #4a9eff;
    }
    
    .radius-search {
      display: flex;
      gap: 10px;
      align-items: flex-end;
    }
    
    .radius-btn {
      padding: 8px 16px;
      background: #4a9eff;
      color: white;
      border: none;
      border-radius: 4px;
      font-size: 13px;
      cursor: pointer;
      transition: background 0.2s;
      height: 35px;
    }
    
    .radius-btn:hover:not(:disabled) {
      background: #3a8eef;
    }
    
    .radius-btn:disabled {
      background: #3a3a3a;
      cursor: not-allowed;
    }
    
    .clear-filters {
      padding: 8px 16px;
      background: #666;
      color: white;
      border: none;
      border-radius: 4px;
      font-size: 13px;
      cursor: pointer;
      transition: background 0.2s;
    }
    
    .clear-filters:hover:not(:disabled) {
      background: #555;
    }
    
    .clear-filters:disabled {
      background: #3a3a3a;
      cursor: not-allowed;
    }
    
    #map {
      flex: 1;
      background: #1a1a1a;
    }
    
    .popup-content {
      min-width: 250px;
    }
    
    .popup-content h4 {
      margin: 0 0 8px 0;
      font-size: 15px;
    }
    
    .popup-content h4 a {
      color: #0066cc;
      text-decoration: none;
    }
    
    .popup-content h4 a:hover {
      text-decoration: underline;
    }
    
    .popup-location {
      color: #666;
      font-size: 13px;
      margin: 4px 0;
    }
    
    .popup-service {
      color: #4a9eff;
      font-size: 12px;
      margin: 4px 0;
      font-weight: 500;
    }
    
    .popup-classification {
      background: #8b0000;
      color: white;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: bold;
      display: inline-block;
      margin: 4px 0;
    }
    
    .popup-description {
      color: #333;
      font-size: 13px;
      margin: 8px 0;
      line-height: 1.4;
    }
    
    .popup-tags, .popup-topics {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 8px;
    }
    
    .popup-tag, .popup-topic {
      padding: 2px 6px;
      background: #f0f0f0;
      border-radius: 3px;
      font-size: 11px;
      color: #666;
    }
    
    .popup-topic {
      background: #e8f4ff;
      color: #0066cc;
    }
    
    .popup-date {
      color: #999;
      font-size: 11px;
      margin-top: 8px;
    }
    
    .popup-coords {
      color: #999;
      font-size: 10px;
      margin-top: 4px;
      font-family: monospace;
    }
    
    .no-results {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      text-align: center;
      color: #999;
      z-index: 1000;
      background: #2a2a2a;
      padding: 30px;
      border-radius: 8px;
      border: 1px solid #3a3a3a;
    }
    
    .loading {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 1000;
      background: #2a2a2a;
      padding: 30px;
      border-radius: 8px;
      border: 1px solid #3a3a3a;
      text-align: center;
      min-width: 350px;
    }
    
    .loading p {
      color: #e0e0e0;
      margin: 10px 0;
    }
    
    .progress-bar-container {
      width: 100%;
      height: 20px;
      background: #1a1a1a;
      border-radius: 10px;
      overflow: hidden;
      margin: 15px 0;
      border: 1px solid #3a3a3a;
    }
    
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #4a9eff 0%, #3a8eef 100%);
      border-radius: 10px;
      transition: width 0.3s ease;
      position: relative;
      overflow: hidden;
    }
    
    .progress-bar::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      bottom: 0;
      right: 0;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(255, 255, 255, 0.3) 50%,
        transparent 100%
      );
      animation: shimmer 2s infinite;
    }
    
    @keyframes shimmer {
      0% {
        transform: translateX(-100%);
      }
      100% {
        transform: translateX(100%);
      }
    }
    
    .progress-text {
      font-size: 14px;
      color: #4a9eff;
      font-weight: bold;
      margin-top: 5px;
    }
    
    .loading-error {
      color: #ff4444;
      margin-top: 15px;
      font-size: 13px;
    }
    
    .loading-success {
      color: #4eff4a;
      margin-top: 10px;
      font-size: 13px;
    }
    
    .pulse {
      animation: pulse 1.5s ease-in-out infinite;
    }
    
    @keyframes pulse {
      0%, 100% {
        opacity: 1;
      }
      50% {
        opacity: 0.7;
      }
    }
    
    .fade-out {
      animation: fadeOut 0.5s ease-in-out forwards;
    }
    
    @keyframes fadeOut {
      from {
        opacity: 1;
      }
      to {
        opacity: 0;
      }
    }
    
    .radius-circle {
      fill: #4a9eff;
      fill-opacity: 0.1;
      stroke: #4a9eff;
      stroke-width: 2;
      stroke-opacity: 0.5;
    }
    
    .divider {
      width: 100%;
      height: 1px;
      background: #3a3a3aff;
      margin: 10px 0;
    }
    
    @media (max-width: 768px) {
      .filters {
        flex-direction: column;
      }
      
      .filter-group {
        min-width: 100%;
      }
      
      h1 {
        font-size: 18px;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-top">
      <h1>
        <span>Offchain Intelligence</span>
        <span class="classification-badge">HIGHLY SENSITIVE</span>
      </h1>
      <a href="/" class="back-link">← Back to Home</a>
    </div>
    
    <div class="filters">
      <div class="filter-group" style="flex: 2;">
        <label class="filter-label">Saved Filter Sets</label>
        <div class="preset-filters" id="presetFilters"></div>
      </div>
      
      <div class="filter-group">
        <label class="filter-label">Search</label>
        <input type="text" id="searchInput" placeholder="Search title, location, service...">
      </div>
      
      <button class="clear-filters" id="clearFilters">Clear All</button>
    </div>
    
    <div class="divider"></div>
    
    <div class="filters">
      <div class="filter-group">
        <label class="filter-label">Radius Search (km)</label>
        <div class="radius-search">
          <input type="number" id="radiusInput" placeholder="Radius" min="0.5" max="500" step="0.5">
          <button class="radius-btn" id="radiusBtn">Set Radius</button>
          <button class="radius-btn" id="clearRadiusBtn" style="background: #666;">Clear</button>
        </div>
      </div>
      
      <div class="filter-group" style="flex: 2;">
        <label class="filter-label">
          Topics <span class="stats">(${allTopics.length})</span>
        </label>
        <div class="tag-filters" id="topicFilters">
          ${allTopics.map(topic => `
            <button class="topic-filter" data-topic="${topic}">
              ${topic}
            </button>
          `).join('')}
        </div>
      </div>
      
      <div class="filter-group">
        <label class="filter-label">
          Tags <span class="stats">(${allTags.length})</span>
        </label>
        <div class="tag-filters" id="tagFilters">
          ${allTags.map(tag => `
            <button class="tag-filter" data-tag="${tag}">
              ${tag}
            </button>
          `).join('')}
        </div>
      </div>
    </div>
    
    <div class="stats" id="stats" style="margin-top: 10px;">
      Showing <span id="visibleCount">${locationsData.length}</span> of ${locationsData.length} locations
      <span id="radiusInfo"></span>
    </div>
  </div>
  
  <div id="map">
    <div class="loading" id="loading">
      <p><strong>Loading Map</strong></p>
      <div class="progress-bar-container">
        <div class="progress-bar" id="progressBar" style="width: 0%"></div>
      </div>
      <div class="progress-text" id="progressText">0%</div>
      <p class="loading-status" id="loadingStatus">Initializing map...</p>
    </div>
  </div>
  
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  
  <script>
    // All location data
    const allLocations = ${JSON.stringify(locationsData)};
    
    // Filter presets
    const filterPresets = ${JSON.stringify(filterPresets)};
    
    // State
    let map;
    let markerClusterGroup;
    let allMarkers = [];
    let radiusCircle = null;
    let radiusCenter = null;
    let activeFilters = {
      search: '',
      tags: [],
      topics: [],
      dateRange: null,
      radiusKm: null,
      radiusCenter: null
    };
    let activePreset = null;
    
    // Initialize map with dark theme
    function initMap() {
      // Update loading status
      const loadingStatus = document.getElementById('loadingStatus');
      if (loadingStatus) {
        loadingStatus.textContent = 'Initializing map tiles...';
      }
      
      map = L.map('map').setView([22.3193, 114.1694], 11); // Center on Hong Kong
      
      // Use dark tile layer
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  attribution: '© OpenStreetMap, © CARTO', subdomains: 'abcd', maxZoom: 19
}).addTo(map);
      
      // Update status
      if (loadingStatus) {
        loadingStatus.textContent = 'Setting up clustering...';
      }
      
      // Initialize marker cluster group
      markerClusterGroup = L.markerClusterGroup({
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        maxClusterRadius: 50
      });
      
      map.addLayer(markerClusterGroup);
      
      // Add click handler for radius search
      map.on('click', function(e) {
        const radiusInput = document.getElementById('radiusInput');
        const radius = parseFloat(radiusInput.value);
        if (radius && radius > 0) {
          setRadiusSearch(e.latlng, radius);
        }
      });
      
      // Update status
      if (loadingStatus) {
        loadingStatus.textContent = 'Map ready, loading locations...';
      }
    }
    
    // Calculate distance between two points in km
    function calculateDistance(lat1, lon1, lat2, lon2) {
      const R = 6371; // Earth's radius in km
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    }
    
    // Set radius search
    function setRadiusSearch(center, radiusKm) {
      // Remove existing circle
      if (radiusCircle) {
        map.removeLayer(radiusCircle);
      }
      
      // Add new circle
      radiusCircle = L.circle(center, {
        radius: radiusKm * 1000, // Convert km to meters
        className: 'radius-circle'
      }).addTo(map);
      
      // Update state
      radiusCenter = center;
      activeFilters.radiusKm = radiusKm;
      activeFilters.radiusCenter = [center.lat, center.lng];
      
      // Update display
      document.getElementById('radiusInfo').textContent = 
        ' | Radius: ' + radiusKm + 'km from ' + center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
      
      updateMarkers();
    }
    
    // Clear radius search
    function clearRadiusSearch() {
      if (radiusCircle) {
        map.removeLayer(radiusCircle);
        radiusCircle = null;
      }
      radiusCenter = null;
      activeFilters.radiusKm = null;
      activeFilters.radiusCenter = null;
      document.getElementById('radiusInfo').textContent = '';
      document.getElementById('radiusInput').value = '';
      updateMarkers();
    }
    
    // Create custom icon for markers
    function createIcon(loc) {
      const color = loc.classification === 'HIGHLY SENSITIVE' ? '#8b0000' : '#4a9eff';
      return L.divIcon({
        html: '<div style="background:' + color + ';width:10px;height:10px;border-radius:50%;border:2px solid white;"></div>',
        iconSize: [14, 14],
        className: 'custom-marker'
      });
    }
    
    // Create popup content
    function createPopupContent(loc) {
      const date = loc.date ? new Date(loc.date).toLocaleDateString() : '';
      return \`
        <div class="popup-content">
          <h4><a href="/\${loc.slug}">\${loc.title}</a></h4>
          \${loc.classification ? \`<span class="popup-classification">\${loc.classification}</span>\` : ''}
          \${loc.serviceType ? \`<div class="popup-service">Service: \${loc.serviceType}</div>\` : ''}
          \${loc.location ? \`<div class="popup-location">📍 \${loc.location}</div>\` : ''}
          \${loc.description ? \`<div class="popup-description">\${loc.description}</div>\` : ''}
          \${loc.topics && loc.topics.length > 0 ? \`
            <div class="popup-topics">
              \${loc.topics.map(topic => \`<span class="popup-topic">\${topic}</span>\`).join('')}
            </div>
          \` : ''}
          \${loc.tags.length > 0 ? \`
            <div class="popup-tags">
              \${loc.tags.map(tag => \`<span class="popup-tag">\${tag}</span>\`).join('')}
            </div>
          \` : ''}
          \${date ? \`<div class="popup-date">Date: \${date}</div>\` : ''}
          \${loc.coordinates ? \`<div class="popup-coords">\${loc.coordinates[0].toFixed(6)}, \${loc.coordinates[1].toFixed(6)}</div>\` : ''}
        </div>
      \`;
    }
    
    // Add all markers with progress tracking
    async function addAllMarkers() {
      const loadingEl = document.getElementById('loading');
      const progressBar = document.getElementById('progressBar');
      const progressText = document.getElementById('progressText');
      const loadingStatus = document.getElementById('loadingStatus');
      
      const total = allLocations.length;
      let processed = 0;
      
      // Update progress
      function updateProgress(status) {
        processed++;
        const percentage = Math.round((processed / total) * 100);
        
        if (progressBar) {
          progressBar.style.width = percentage + '%';
        }
        if (progressText) {
          progressText.textContent = percentage + '%';
        }
        if (loadingStatus && status) {
          loadingStatus.textContent = status;
        }
      }
      
      // Initial status
      if (loadingStatus) {
        loadingStatus.textContent = 'Processing ' + total + ' locations...';
      }
      
      for (let i = 0; i < allLocations.length; i++) {
        const loc = allLocations[i];
        
        if (loc.coordinates) {
          const marker = L.marker(loc.coordinates, { icon: createIcon(loc) });
          marker.bindPopup(createPopupContent(loc));
          marker.locationData = loc;
          allMarkers.push(marker);
          
          // Update progress
          updateProgress('Loaded: ' + loc.title);
        } else {
          // Still count as processed even if no coordinates
          updateProgress('Skipped: ' + loc.title + ' (no coordinates)');
        }
        
        // Add small delay for smooth animation
        if (i % 10 === 0) {
          await new Promise(resolve => setTimeout(resolve, 10));
        }
      }
      
      // Final loading steps
      if (loadingStatus) {
        loadingStatus.textContent = 'Finalizing map...';
      }
      
      // Small delay before removing loading screen
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Remove loading message with fade effect
      if (loadingEl) {
        loadingEl.style.transition = 'opacity 0.5s';
        loadingEl.style.opacity = '0';
        setTimeout(() => loadingEl.remove(), 500);
      }
      
      // Initial display
      updateMarkers();
    }
    
    // Apply preset filter
    function applyPreset(preset) {
      activeFilters.tags = [...preset.tags];
      activeFilters.topics = [...preset.topics];
      
      // Update UI
      document.querySelectorAll('.tag-filter').forEach(btn => {
        btn.classList.toggle('active', activeFilters.tags.includes(btn.dataset.tag));
      });
      
      document.querySelectorAll('.topic-filter').forEach(btn => {
        btn.classList.toggle('active', activeFilters.topics.includes(btn.dataset.topic));
      });
      
      updateMarkers();
    }
    
    // Filter markers based on active filters
    function filterMarkers() {
      const { search, tags, topics, radiusKm, radiusCenter } = activeFilters;
      
      return allMarkers.filter(marker => {
        const loc = marker.locationData;
        
        // Search filter
        if (search) {
          const searchLower = search.toLowerCase();
          const matchesSearch = 
            loc.title.toLowerCase().includes(searchLower) ||
            (loc.location && loc.location.toLowerCase().includes(searchLower)) ||
            (loc.serviceType && loc.serviceType.toLowerCase().includes(searchLower)) ||
            (loc.description && loc.description.toLowerCase().includes(searchLower));
          
          if (!matchesSearch) return false;
        }
        
        // Tag filter
        if (tags.length > 0) {
          const hasTag = tags.some(tag => loc.tags.includes(tag));
          if (!hasTag) return false;
        }
        
        // Topic filter
        if (topics.length > 0) {
          const hasTopic = topics.some(topic => loc.topics.includes(topic));
          if (!hasTopic) return false;
        }
        
        // Radius filter
        if (radiusKm && radiusCenter) {
          const distance = calculateDistance(
            radiusCenter[0], radiusCenter[1],
            loc.coordinates[0], loc.coordinates[1]
          );
          if (distance > radiusKm) return false;
        }
        
        return true;
      });
    }
    
    // Update displayed markers
    function updateMarkers() {
      markerClusterGroup.clearLayers();
      
      const visibleMarkers = filterMarkers();
      visibleMarkers.forEach(marker => {
        markerClusterGroup.addLayer(marker);
      });
      
      // Update stats
      document.getElementById('visibleCount').textContent = visibleMarkers.length;
      
      // Show/hide no results message
      const existingNoResults = document.querySelector('.no-results');
      if (existingNoResults) existingNoResults.remove();
      
      if (visibleMarkers.length === 0 && allMarkers.length > 0) {
        const noResults = document.createElement('div');
        noResults.className = 'no-results';
        noResults.innerHTML = \`
          <h3>No locations found</h3>
          <p>Try adjusting your filters or search radius</p>
        \`;
        document.getElementById('map').appendChild(noResults);
      } else if (visibleMarkers.length > 0 && !activeFilters.radiusCenter) {
        // Fit map to visible markers (only if not in radius mode)
        const group = L.featureGroup(visibleMarkers);
        map.fitBounds(group.getBounds().pad(0.1));
      }
      
      // Update clear button state
      const hasActiveFilters = activeFilters.search || 
                               activeFilters.tags.length > 0 || 
                               activeFilters.topics.length > 0 ||
                               activeFilters.radiusKm;
      document.getElementById('clearFilters').disabled = !hasActiveFilters;
    }
    
    // Setup event listeners
    function setupEventListeners() {
      // Preset filters
      const presetContainer = document.getElementById('presetFilters');
      filterPresets.forEach(preset => {
        const btn = document.createElement('button');
        btn.className = 'preset-btn';
        btn.textContent = preset.name;
        btn.addEventListener('click', () => {
          // Toggle active state
          document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
          if (activePreset !== preset.name) {
            btn.classList.add('active');
            activePreset = preset.name;
            applyPreset(preset);
          } else {
            activePreset = null;
            activeFilters.tags = [];
            activeFilters.topics = [];
            updateMarkers();
          }
        });
        presetContainer.appendChild(btn);
      });
      
      // Search input
      const searchInput = document.getElementById('searchInput');
      let searchTimeout;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
          activeFilters.search = e.target.value;
          updateMarkers();
        }, 300);
      });
      
      // Tag filters
      document.querySelectorAll('.tag-filter').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const tag = e.target.dataset.tag;
          const index = activeFilters.tags.indexOf(tag);
          
          if (index > -1) {
            activeFilters.tags.splice(index, 1);
            e.target.classList.remove('active');
          } else {
            activeFilters.tags.push(tag);
            e.target.classList.add('active');
          }
          
          // Clear preset selection
          document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
          activePreset = null;
          
          updateMarkers();
        });
      });
      
      // Topic filters
      document.querySelectorAll('.topic-filter').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const topic = e.target.dataset.topic;
          const index = activeFilters.topics.indexOf(topic);
          
          if (index > -1) {
            activeFilters.topics.splice(index, 1);
            e.target.classList.remove('active');
          } else {
            activeFilters.topics.push(topic);
            e.target.classList.add('active');
          }
          
          // Clear preset selection
          document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
          activePreset = null;
          
          updateMarkers();
        });
      });
      
      // Radius search
      document.getElementById('radiusBtn').addEventListener('click', () => {
        const radius = parseFloat(document.getElementById('radiusInput').value);
        if (radius && radius > 0) {
          alert('Click on the map to set the center point for radius search');
        }
      });
      
      document.getElementById('clearRadiusBtn').addEventListener('click', clearRadiusSearch);
      
      // Clear filters
      document.getElementById('clearFilters').addEventListener('click', () => {
        activeFilters = {
          search: '',
          tags: [],
          topics: [],
          dateRange: null,
          radiusKm: null,
          radiusCenter: null
        };
        
        document.getElementById('searchInput').value = '';
        document.querySelectorAll('.tag-filter.active').forEach(btn => {
          btn.classList.remove('active');
        });
        document.querySelectorAll('.topic-filter.active').forEach(btn => {
          btn.classList.remove('active');
        });
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        activePreset = null;
        
        clearRadiusSearch();
        updateMarkers();
      });
    }
    
    // Initialize everything with progress tracking
    async function initialize() {
      const loadingEl = document.getElementById('loading');
      const loadingStatus = document.getElementById('loadingStatus');
      
      try {
        // Start with a small delay for smooth loading experience
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Initialize map
        initMap();
        
        // Setup event listeners
        if (loadingStatus) {
          loadingStatus.textContent = 'Configuring filters...';
        }
        await new Promise(resolve => setTimeout(resolve, 100));
        setupEventListeners();
        
        // Load all markers with progress
        await addAllMarkers();
        
      } catch (error) {
        console.error('Map initialization error:', error);
        
        // Show error in loading screen
        if (loadingEl) {
          const progressBar = document.getElementById('progressBar');
          const progressText = document.getElementById('progressText');
          
          if (progressBar) {
            progressBar.style.background = 'linear-gradient(90deg, #ff4444 0%, #cc0000 100%)';
            progressBar.style.width = '100%';
          }
          if (progressText) {
            progressText.textContent = 'Error';
            progressText.style.color = '#ff4444';
          }
          if (loadingStatus) {
            loadingStatus.innerHTML = '<div class="loading-error">Failed to initialize map: ' + error.message + '<br>Please refresh the page to try again.</div>';
          }
        }
      }
    }
    
    // Start initialization
    initialize();
  </script>
</body>
</html>`

      // Write the file using Quartz's write helper
      const fp = await write({
        ctx: ctx,
        slug: "map" as FullSlug,
        ext: ".html",
        content: mapHtml,
      })
      
      fps.push(fp)
      return fps
    },
  }
}