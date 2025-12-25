import { QuartzTransformerPlugin } from "../types"
import { Root } from "mdast"
import { VFile } from "vfile"
import { visit } from "unist-util-visit"
import { toString } from "mdast-util-to-string"

export interface MapOptions {
  // Extract location from specific frontmatter fields
  locationFields?: string[]
  // Extract coordinates from specific frontmatter fields  
  coordinateFields?: string[]
  // Auto-geocode locations without coordinates
  autoGeocode?: boolean
}

const defaultOptions: MapOptions = {
  locationFields: ["location", "place", "city", "address"],
  coordinateFields: ["coordinates", "coords", "latlon", "geo"],
  autoGeocode: true,
}

export const MapLocations: QuartzTransformerPlugin<MapOptions> = (userOpts?: MapOptions) => {
  const opts = { ...defaultOptions, ...userOpts }
  
  return {
    name: "MapLocations",
    markdownPlugins() {
      return [
        () => {
          return (tree: Root, file: VFile) => {
            const frontmatter = file.data.frontmatter || {}
            
            // Check for location in frontmatter
            let location: string | undefined
            let coordinates: [number, number] | undefined
            
            // Extract location from configured fields
            for (const field of opts.locationFields!) {
              if (frontmatter[field]) {
                location = String(frontmatter[field])
                break
              }
            }
            
            // Extract coordinates from configured fields
            for (const field of opts.coordinateFields!) {
              if (frontmatter[field]) {
                const coords = frontmatter[field]
                
                // Handle different coordinate formats
                if (Array.isArray(coords) && coords.length === 2) {
                  coordinates = [Number(coords[0]), Number(coords[1])]
                } else if (typeof coords === "string") {
                  // Parse string formats like "lat,lon" or "lat, lon"
                  const parts = coords.split(",").map(s => s.trim())
                  if (parts.length === 2) {
                    const lat = Number(parts[0])
                    const lon = Number(parts[1])
                    if (!isNaN(lat) && !isNaN(lon)) {
                      coordinates = [lat, lon]
                    }
                  }
                } else if (typeof coords === "object" && coords !== null) {
                  // Handle object format like {lat: 40, lon: -74}
                  if ("lat" in coords && "lon" in coords) {
                    coordinates = [Number(coords.lat), Number(coords.lon)]
                  } else if ("latitude" in coords && "longitude" in coords) {
                    coordinates = [Number(coords.latitude), Number(coords.longitude)]
                  }
                }
                
                if (coordinates) break
              }
            }
            
            // Store extracted data in frontmatter for later use
            if (location) {
              file.data.frontmatter!.location = location
            }
            if (coordinates) {
              file.data.frontmatter!.coordinates = coordinates
            }
            
            // Also extract location from content if configured
            // Look for location patterns in the content
            const locationPatterns = [
              /📍\s*([^\n]+)/,  // Pin emoji followed by location
              /Location:\s*([^\n]+)/i,  // "Location:" label
              /Place:\s*([^\n]+)/i,  // "Place:" label
            ]
            
            if (!location) {
              visit(tree, "paragraph", (node) => {
                const text = toString(node)
                for (const pattern of locationPatterns) {
                  const match = text.match(pattern)
                  if (match) {
                    location = match[1].trim()
                    file.data.frontmatter!.location = location
                    break
                  }
                }
              })
            }
          }
        },
      ]
    },
  }
}

// Add type declarations for the frontmatter fields
declare module "vfile" {
  interface DataMap {
    frontmatter: {
      location?: string
      coordinates?: [number, number]
      [key: string]: any
    }
  }
}