import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import mapScript from "./scripts/map.inline"
import mapStyle from "./styles/map.scss"

interface MapOptions {
  title?: string
  height?: string
  defaultZoom?: number
  defaultCenter?: [number, number]
  clusterMarkers?: boolean
  showSearch?: boolean
}

const defaultOptions: MapOptions = {
  title: "Content Map",
  height: "600px",
  defaultZoom: 2,
  defaultCenter: [20, 0],
  clusterMarkers: true,
  showSearch: true,
}

export default ((userOpts?: MapOptions) => {
  const opts = { ...defaultOptions, ...userOpts }
  
  const Map: QuartzComponent = (props: QuartzComponentProps) => {
    const { allFiles } = props
    
    // Extract location data from all files
    const locations = allFiles
      .filter(file => file.frontmatter?.location)
      .map(file => ({
        slug: file.slug!,
        title: file.frontmatter?.title || file.slug!,
        location: file.frontmatter.location,
        coordinates: file.frontmatter.coordinates,
        description: file.description,
        tags: file.frontmatter?.tags || []
      }))
    
    return (
      <div class="map-container">
        {opts.title && <h2>{opts.title}</h2>}
        {opts.showSearch && (
          <div class="map-search">
            <input 
              type="text" 
              id="map-search-input" 
              placeholder="Search locations..."
            />
          </div>
        )}
        <div 
          id="quartz-map" 
          data-locations={JSON.stringify(locations)}
          data-options={JSON.stringify(opts)}
          style={`height: ${opts.height}`}
        >
          <noscript>
            <p>JavaScript is required to view the interactive map.</p>
            <ul class="map-fallback">
              {locations.map(loc => (
                <li>
                  <a href={`/${loc.slug}`}>{loc.title}</a>
                  {loc.location && <span> - {loc.location}</span>}
                </li>
              ))}
            </ul>
          </noscript>
        </div>
      </div>
    )
  }
  
  Map.css = mapStyle
  Map.afterDOMLoaded = mapScript
  
  return Map
}) satisfies QuartzComponentConstructor