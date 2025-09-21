// Import Leaflet from CDN
const loadLeaflet = () => {
  return new Promise((resolve) => {
    // Check if already loaded
    if (window.L) {
      resolve(window.L)
      return
    }
    
    // Load Leaflet CSS
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(link)
    
    // Load Leaflet JS
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => {
      // Load MarkerCluster plugin if clustering is enabled
      const clusterCSS = document.createElement('link')
      clusterCSS.rel = 'stylesheet'
      clusterCSS.href = 'https://unpkg.com/leaflet.markerclusterer@1.5.3/dist/MarkerCluster.css'
      document.head.appendChild(clusterCSS)
      
      const clusterDefaultCSS = document.createElement('link')
      clusterDefaultCSS.rel = 'stylesheet'
      clusterDefaultCSS.href = 'https://unpkg.com/leaflet.markerclusterer@1.5.3/dist/MarkerCluster.Default.css'
      document.head.appendChild(clusterDefaultCSS)
      
      const clusterScript = document.createElement('script')
      clusterScript.src = 'https://unpkg.com/leaflet.markerclusterer@1.5.3/dist/leaflet.markercluster.js'
      clusterScript.onload = () => resolve(window.L)
      document.head.appendChild(clusterScript)
    }
    document.head.appendChild(script)
  })
}

// Geocoding function using Nominatim (OpenStreetMap)
const geocodeLocation = async (location: string): Promise<[number, number] | null> => {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(location)}&limit=1`
    )
    const data = await response.json()
    if (data && data.length > 0) {
      return [parseFloat(data[0].lat), parseFloat(data[0].lon)]
    }
  } catch (error) {
    console.error(`Failed to geocode location: ${location}`, error)
  }
  return null
}

// Initialize map function
const initializeMap = async () => {
  const mapContainer = document.getElementById('quartz-map')
  if (!mapContainer) return
  
  // Get data from attributes
  const locations = JSON.parse(mapContainer.dataset.locations || '[]')
  const options = JSON.parse(mapContainer.dataset.options || '{}')
  
  // Load Leaflet
  await loadLeaflet()
  
  // Create map
  const map = L.map('quartz-map').setView(
    options.defaultCenter || [20, 0],
    options.defaultZoom || 2
  )
  
  // Add OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(map)
  
  // Create marker cluster group if enabled
  const markers = options.clusterMarkers 
    ? L.markerClusterGroup() 
    : L.layerGroup()
  
  // Process locations and add markers
  const processedLocations: any[] = []
  
  for (const loc of locations) {
    let coords: [number, number] | null = null
    
    // Use provided coordinates or geocode the location
    if (loc.coordinates && Array.isArray(loc.coordinates) && loc.coordinates.length === 2) {
      coords = loc.coordinates
    } else if (loc.location) {
      coords = await geocodeLocation(loc.location)
    }
    
    if (coords) {
      const marker = L.marker(coords)
      
      // Create popup content
      const popupContent = `
        <div class="map-popup">
          <h4><a href="/${loc.slug}">${loc.title}</a></h4>
          ${loc.location ? `<p class="location-name">${loc.location}</p>` : ''}
          ${loc.description ? `<p class="location-description">${loc.description}</p>` : ''}
          ${loc.tags && loc.tags.length > 0 ? `
            <div class="location-tags">
              ${loc.tags.map((tag: string) => `<span class="tag">#${tag}</span>`).join(' ')}
            </div>
          ` : ''}
        </div>
      `
      
      marker.bindPopup(popupContent)
      markers.addLayer(marker)
      
      processedLocations.push({
        ...loc,
        coordinates: coords
      })
    }
  }
  
  markers.addTo(map)
  
  // Fit map to markers if there are any
  if (processedLocations.length > 0) {
    const group = L.featureGroup(
      processedLocations.map(loc => L.marker(loc.coordinates))
    )
    map.fitBounds(group.getBounds().pad(0.1))
  }
  
  // Add search functionality if enabled
  if (options.showSearch) {
    const searchInput = document.getElementById('map-search-input') as HTMLInputElement
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const searchTerm = (e.target as HTMLInputElement).value.toLowerCase()
        
        // Clear existing markers
        markers.clearLayers()
        
        // Filter and re-add markers
        processedLocations
          .filter(loc => 
            loc.title.toLowerCase().includes(searchTerm) ||
            (loc.location && loc.location.toLowerCase().includes(searchTerm)) ||
            (loc.tags && loc.tags.some((tag: string) => tag.toLowerCase().includes(searchTerm)))
          )
          .forEach(loc => {
            const marker = L.marker(loc.coordinates)
            const popupContent = `
              <div class="map-popup">
                <h4><a href="/${loc.slug}">${loc.title}</a></h4>
                ${loc.location ? `<p class="location-name">${loc.location}</p>` : ''}
                ${loc.description ? `<p class="location-description">${loc.description}</p>` : ''}
                ${loc.tags && loc.tags.length > 0 ? `
                  <div class="location-tags">
                    ${loc.tags.map((tag: string) => `<span class="tag">#${tag}</span>`).join(' ')}
                  </div>
                ` : ''}
              </div>
            `
            marker.bindPopup(popupContent)
            markers.addLayer(marker)
          })
      })
    }
  }
  
  // Store map instance for cleanup
  window.quartzMap = map
}

// Initialize on page load
document.addEventListener("nav", () => {
  initializeMap()
  
  // Cleanup function
  window.addCleanup(() => {
    if (window.quartzMap) {
      window.quartzMap.remove()
      window.quartzMap = null
    }
  })
})

// TypeScript declarations
declare global {
  interface Window {
    L: any
    quartzMap: any
    addCleanup: (fn: () => void) => void
  }
}