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
      
      // Count locations
      const locationsData = allFiles
        .filter(f => f.frontmatter?.location || f.frontmatter?.coordinates)
        .map(f => ({
          slug: f.slug || "",
          title: f.frontmatter?.title || f.slug || "Untitled",
          location: f.frontmatter?.location || null,
          coordinates: f.frontmatter?.coordinates || null,
          tags: f.frontmatter?.tags || []
        }))
      
      // Create a simple HTML page with inline map
      const mapHtml = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Map - ${ctx.cfg.configuration.pageTitle}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background: #f5f5f5;
    }
    h1 {
      color: #333;
      margin-bottom: 10px;
    }
    .info {
      color: #666;
      margin-bottom: 20px;
    }
    #map {
      height: 600px;
      border: 1px solid #ddd;
      border-radius: 4px;
      background: white;
    }
    .back-link {
      display: inline-block;
      margin-bottom: 20px;
      color: #0066cc;
      text-decoration: none;
    }
    .back-link:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <a href="/" class="back-link">← Back to Home</a>
  <h1>Content Map</h1>
  <p class="info">Found ${locationsData.length} location(s) in content</p>
  <div id="map"></div>
  
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const locations = ${JSON.stringify(locationsData)};
    
    // Initialize map
    const map = L.map('map').setView([20, 0], 2);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);
    
    // Geocoding function
    async function geocode(location) {
      try {
        const response = await fetch(
          'https://nominatim.openstreetmap.org/search?format=json&q=' + 
          encodeURIComponent(location) + '&limit=1'
        );
        const data = await response.json();
        if (data && data.length > 0) {
          return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
        }
      } catch (error) {
        console.error('Geocoding failed for:', location, error);
      }
      return null;
    }
    
    // Add markers
    const markers = [];
    
    async function addMarkers() {
      for (const loc of locations) {
        let coords = null;
        
        // Use provided coordinates or geocode
        if (loc.coordinates && Array.isArray(loc.coordinates)) {
          coords = loc.coordinates;
        } else if (loc.location) {
          coords = await geocode(loc.location);
          // Add a small delay to avoid rate limiting
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        if (coords) {
          const marker = L.marker(coords);
          const popupContent = '<div>' +
            '<h4><a href="/' + loc.slug + '">' + loc.title + '</a></h4>' +
            (loc.location ? '<p>' + loc.location + '</p>' : '') +
            '</div>';
          marker.bindPopup(popupContent);
          marker.addTo(map);
          markers.push({ marker, coords });
        }
      }
      
      // Fit map to markers
      if (markers.length > 0) {
        const group = L.featureGroup(markers.map(m => m.marker));
        map.fitBounds(group.getBounds().pad(0.1));
      }
    }
    
    addMarkers();
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