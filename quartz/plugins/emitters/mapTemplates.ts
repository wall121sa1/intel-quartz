// Map HTML Templates
// quartz/plugins/emitters/mapTemplates.ts

import { MapLocation, FilterPreset, FooterConfig } from "./mapConfig"

export function generateStyles(): string {
  // Import the compiled CSS at build time
  // This will be handled by the build system
  return `<link rel="stylesheet" href="/map-styles.css">`
}

export function generateHead(title: string): string {
  return `
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  `
}

export function generateHeader(
  allTopics: string[],
  allTags: string[],
  locationsCount: number
): string {
  return `
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
        Showing <span id="visibleCount">${locationsCount}</span> of ${locationsCount} locations
        <span id="radiusInfo"></span>
      </div>
    </div>
  `
}

export function generateLoadingScreen(): string {
  return `
    <div class="loading" id="loading">
      <p><strong>Loading Map</strong></p>
      <div class="progress-bar-container">
        <div class="progress-bar" id="progressBar" style="width: 0%"></div>
      </div>
      <div class="progress-text" id="progressText">0%</div>
      <p class="loading-status" id="loadingStatus">Initializing map...</p>
    </div>
  `
}

export function generateMapContainer(): string {
  return `
    <div id="map">
      ${generateLoadingScreen()}
    </div>
  `
}

// EXPORT generateScriptTags - This was the missing export!
export function generateScriptTags(): string {
  return `
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  `
}

// Export generateFooter
export function generateFooter(footerConfig: FooterConfig): string {
  const currentYear = new Date().getFullYear()
  const { 
    title = "Intelligence Map",
    description = "",
    dataSources = [],
    showStats = true,
    threatLevel = 'moderate',
    operationalStatus = "",
    links = [],
    disclaimer = "",
    copyright = ""
  } = footerConfig
  
  return `
    <footer class="map-footer">
      <div class="footer-content">
        <div class="footer-section">
          <h4>${title}</h4>
          ${description ? `<p>${description}</p>` : ''}
          <p class="footer-classification">
            <span class="classification-badge">HIGHLY SENSITIVE</span>
            <span class="footer-text">Authorized Personnel Only</span>
          </p>
        </div>
        
        ${dataSources.length > 0 ? `
        <div class="footer-section">
          <h4>Data Sources</h4>
          <ul>
            ${dataSources.map(source => `<li>${source}</li>`).join('')}
          </ul>
        </div>
        ` : ''}
        
        ${showStats ? `
        <div class="footer-section">
          <h4>Quick Stats</h4>
          <div class="footer-stats" id="footerStats">
            <div class="stat-item">
              <span class="stat-value" id="totalLocations">--</span>
              <span class="stat-label">Total Locations</span>
            </div>
            <div class="stat-item">
              <span class="stat-value" id="totalCountries">--</span>
              <span class="stat-label">Countries</span>
            </div>
            <div class="stat-item">
              <span class="stat-value" id="lastUpdated">--</span>
              <span class="stat-label">Last Updated</span>
            </div>
          </div>
        </div>
        ` : ''}
        
        <div class="footer-section">
          <h4>Operations</h4>
          ${operationalStatus ? `<p>${operationalStatus}</p>` : ''}
          <p>Threat Level: <span class="threat-level ${threatLevel}">${threatLevel.toUpperCase()}</span></p>
          ${links.length > 0 ? `
          <p class="footer-links">
            ${links.map((link, i) => 
              `${i > 0 ? ' | ' : ''}<a href="${link.url}">${link.text}</a>`
            ).join('')}
          </p>
          ` : ''}
        </div>
      </div>
      
      <div class="footer-bottom">
        ${copyright ? `<p>&copy; ${currentYear} ${copyright}</p>` : ''}
        ${disclaimer ? `
        <p class="footer-disclaimer">
          ${disclaimer}
        </p>
        ` : ''}
      </div>
    </footer>
  `
}