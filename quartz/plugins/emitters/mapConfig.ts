// Map Configuration and Constants
// quartz/plugins/emitters/mapConfig.ts

export interface MapLocation {
  slug: string
  title: string
  location: string | null
  coordinates: [number, number] | null
  tags: string[]
  date: string | null
  description: string
  classification: string | null
  reportType: string | null
  serviceType: string | null
  topics: string[]
}

export interface FilterPreset {
  name: string
  tags: string[]
  topics: string[]
  classification?: string
}

export interface MapConfig {
  defaultCenter: [number, number]
  defaultZoom: number
  clusterRadius: number
  tileLayer: {
    url: string
    attribution: string
  }
}

export interface FooterConfig {
  title?: string
  description?: string
  dataSources?: string[]
  showStats?: boolean
  threatLevel?: 'low' | 'moderate' | 'high' | 'severe' | 'critical'
  operationalStatus?: string
  links?: { text: string, url: string }[]
  disclaimer?: string
  copyright?: string
}

// Export DEFAULT_MAP_CONFIG
export const DEFAULT_MAP_CONFIG: MapConfig = {
  defaultCenter: [22.3193, 114.1694], // Hong Kong
  defaultZoom: 11,
  clusterRadius: 50,
  tileLayer: {
    url: 'https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors © CARTO'
  }
}

// Export DEFAULT_FILTER_PRESETS - This was missing!
export const DEFAULT_FILTER_PRESETS: FilterPreset[] = [
  { name: "SENSITIVE", classification: "SENSITIVE", tags: [], topics: [] },
  { name: "PUBLIC", classification: "PUBLIC", tags: [], topics: [] }
]

// Export DEFAULT_FOOTER_CONFIG
export const DEFAULT_FOOTER_CONFIG: FooterConfig = {
  title: "Offchain Info - Fusing Web3 Intelligence",
  description: "Real-time tracking of Cash to Cryptocurrency Operations worldwide.",
  dataSources: [
    "Field Intelligence Reports",
    "Open Source Intelligence",
  ],
  showStats: true,
  threatLevel: 'moderate',
  operationalStatus: "Active Monitoring",
  links: [
    { text: "Dashboard", url: "/" },
    { text: "Reports", url: "/reports" },
    { text: "Alerts", url: "/alerts" }
  ],
  disclaimer: "This map contains sensitive intelligence data. Unauthorized access, distribution, or use is strictly prohibited and may result in legal action. By accessing this system, you acknowledge that you are authorized to view this content.",
  copyright: "Offchain.Info. All information is proprietary and confidential."
}

// Utility functions for processing location data
export function extractCoordinates(frontmatter: any): [number, number] | null {
  if (frontmatter?.position) {
    const parts = String(frontmatter.position).split(",").map(s => s.trim())
    if (parts.length === 2) {
      const lat = Number(parts[0])
      const lon = Number(parts[1])
      if (!isNaN(lat) && !isNaN(lon)) {
        return [lat, lon]
      }
    }
  } else if (frontmatter?.coordinates) {
    return frontmatter.coordinates
  }
  return null
}

export function extractLocation(frontmatter: any): string | null {
  let location = frontmatter?.location || frontmatter?.Location || null
  
  if (!location && frontmatter?.Topics && Array.isArray(frontmatter.Topics)) {
    const locationTopics = frontmatter.Topics.filter((topic: string) => 
      !['OTC', 'CryptoToCash', 'P2P'].includes(topic)
    )
    if (locationTopics.length > 0) {
      location = locationTopics.join(", ")
    }
  }
  
  return location
}

export function processLocationData(file: any): MapLocation {
  const coords = extractCoordinates(file.frontmatter)
  const location = extractLocation(file.frontmatter)
  
  return {
    slug: file.slug || "",
    title: file.frontmatter?.title || file.slug || "Untitled",
    location: location,
    coordinates: coords,
    tags: file.frontmatter?.tags || [],
    date: file.frontmatter?.date || 
          file.frontmatter?.created || 
          file.frontmatter?.["Intelligence Cut Off Date"] || 
          null,
    description: file.description || file.frontmatter?.description || "",
    classification: file.frontmatter?.Classification || null,
    reportType: file.frontmatter?.["Report Type"] || null,
    serviceType: file.frontmatter?.["Service Type"] || null,
    topics: file.frontmatter?.Topics || [],
  }
}

// Calculate distance between two points in km (Haversine formula)
export function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371 // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
  return R * c
}