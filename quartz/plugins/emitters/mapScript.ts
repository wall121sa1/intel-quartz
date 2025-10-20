// Map JavaScript Functionality

import { MapLocation, FilterPreset, MapConfig, calculateDistance } from "./mapConfig"

export function generateMapScript(
  locations: MapLocation[],
  filterPresets: FilterPreset[],
  config: MapConfig
): string {
  return `
    // Configuration
    const allLocations = ${JSON.stringify(locations)};
    const filterPresets = ${JSON.stringify(filterPresets)};
    const mapConfig = ${JSON.stringify(config)};
    
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
    
    // Calculate distance between two points in km
    ${calculateDistance.toString()}
    
    // Initialize map
    function initMap() {
      const loadingStatus = document.getElementById('loadingStatus');
      if (loadingStatus) {
        loadingStatus.textContent = 'Initializing map tiles...';
      }
      
      map = L.map('map').setView(mapConfig.defaultCenter, mapConfig.defaultZoom);
      
      L.tileLayer(mapConfig.tileLayer.url, {
        attribution: mapConfig.tileLayer.attribution
      }).addTo(map);
      
      if (loadingStatus) {
        loadingStatus.textContent = 'Setting up clustering...';
      }
      
      markerClusterGroup = L.markerClusterGroup({
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        maxClusterRadius: mapConfig.clusterRadius
      });
      
      map.addLayer(markerClusterGroup);
      
      map.on('click', function(e) {
        const radiusInput = document.getElementById('radiusInput');
        const radius = parseFloat(radiusInput.value);
        if (radius && radius > 0) {
          setRadiusSearch(e.latlng, radius);
        }
      });
      
      if (loadingStatus) {
        loadingStatus.textContent = 'Map ready, loading locations...';
      }
    }
    
    // Set radius search
    function setRadiusSearch(center, radiusKm) {
      if (radiusCircle) {
        map.removeLayer(radiusCircle);
      }
      
      radiusCircle = L.circle(center, {
        radius: radiusKm * 1000,
        className: 'radius-circle'
      }).addTo(map);
      
      radiusCenter = center;
      activeFilters.radiusKm = radiusKm;
      activeFilters.radiusCenter = [center.lat, center.lng];
      
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
      const color = loc.classification === 'SENSITIVE' ? '#8b0000' : '#4a9eff';
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
          updateProgress('Loaded: ' + loc.title);
        } else {
          updateProgress('Skipped: ' + loc.title + ' (no coordinates)');
        }
        
        if (i % 10 === 0) {
          await new Promise(resolve => setTimeout(resolve, 10));
        }
      }
      
      if (loadingStatus) {
        loadingStatus.textContent = 'Finalizing map...';
      }
      
      // Update footer statistics
      updateFooterStats();
      
      await new Promise(resolve => setTimeout(resolve, 500));
      
      if (loadingEl) {
        loadingEl.style.transition = 'opacity 0.5s';
        loadingEl.style.opacity = '0';
        setTimeout(() => loadingEl.remove(), 500);
      }
      
      updateMarkers();
    }
    
    // Update footer statistics
    function updateFooterStats() {
      // Total locations
      const totalLocationsEl = document.getElementById('totalLocations');
      if (totalLocationsEl) {
        totalLocationsEl.textContent = allLocations.length.toString();
      }
      
      // Count unique countries/regions from topics
      const countries = new Set();
      allLocations.forEach(loc => {
        if (loc.topics) {
          loc.topics.forEach(topic => {
            // Filter out non-location topics
            if (!['ATM','CashDesk'].includes(topic)) {
              countries.add(topic);
            }
          });
        }
      });
      
      const totalCountriesEl = document.getElementById('totalCountries');
      if (totalCountriesEl) {
        totalCountriesEl.textContent = countries.size.toString();
      }
      
      // Last updated (most recent date from data)
      let mostRecentDate = null;
      allLocations.forEach(loc => {
        if (loc.date) {
          const date = new Date(loc.date);
          if (!mostRecentDate || date > mostRecentDate) {
            mostRecentDate = date;
          }
        }
      });
      
      const lastUpdatedEl = document.getElementById('lastUpdated');
      if (lastUpdatedEl) {
        if (mostRecentDate) {
          // Format as "DD MMM"
          const options = { day: 'numeric', month: 'short' };
          lastUpdatedEl.textContent = mostRecentDate.toLocaleDateString('en-US', options);
        } else {
          lastUpdatedEl.textContent = 'N/A';
        }
      }
    }
    
    // Apply preset filter
    function applyPreset(preset) {
      activeFilters.tags = [...preset.tags];
      activeFilters.topics = [...preset.topics];
      
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
        
        if (search) {
          const searchLower = search.toLowerCase();
          const matchesSearch = 
            loc.title.toLowerCase().includes(searchLower) ||
            (loc.location && loc.location.toLowerCase().includes(searchLower)) ||
            (loc.serviceType && loc.serviceType.toLowerCase().includes(searchLower)) ||
            (loc.description && loc.description.toLowerCase().includes(searchLower));
          
          if (!matchesSearch) return false;
        }
        
        if (tags.length > 0) {
          const hasTag = tags.some(tag => loc.tags.includes(tag));
          if (!hasTag) return false;
        }
        
        if (topics.length > 0) {
          const hasTopic = topics.some(topic => loc.topics.includes(topic));
          if (!hasTopic) return false;
        }
        
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
      
      document.getElementById('visibleCount').textContent = visibleMarkers.length;
      
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
        const group = L.featureGroup(visibleMarkers);
        map.fitBounds(group.getBounds().pad(0.1));
      }
      
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
    
    // Initialize everything
    async function initialize() {
      const loadingEl = document.getElementById('loading');
      const loadingStatus = document.getElementById('loadingStatus');
      
      try {
        await new Promise(resolve => setTimeout(resolve, 100));
        initMap();
        
        if (loadingStatus) {
          loadingStatus.textContent = 'Configuring filters...';
        }
        await new Promise(resolve => setTimeout(resolve, 100));
        setupEventListeners();
        
        await addAllMarkers();
        
      } catch (error) {
        console.error('Map initialization error:', error);
        
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
  `
}