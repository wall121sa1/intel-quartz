import { QuartzEmitterPlugin } from "../types"
import { FilePath, FullSlug } from "../../util/path"
import { write } from "./helpers"
import { 
  DEFAULT_MAP_CONFIG, 
  DEFAULT_FILTER_PRESETS,
  DEFAULT_FOOTER_CONFIG,
  processLocationData,
  MapLocation 
} from "./mapConfig"
import {
  generateHead,
  generateHeader,
  generateMapContainer,
  generateScriptTags,
  generateFooter
} from "./mapTemplates"
import { generateMapScript } from "./mapScript"
import mapStyles from "./styles/map.scss"

export interface MapPageOptions {
  title?: string
  slug?: FullSlug
  config?: typeof DEFAULT_MAP_CONFIG
  filterPresets?: typeof DEFAULT_FILTER_PRESETS
  footerConfig?: typeof DEFAULT_FOOTER_CONFIG
}

const defaultOptions: MapPageOptions = {
  title: "Intelligence Map",
  slug: "map" as FullSlug,
  config: DEFAULT_MAP_CONFIG,
  filterPresets: DEFAULT_FILTER_PRESETS,
  footerConfig: DEFAULT_FOOTER_CONFIG
}

export const MapPage: QuartzEmitterPlugin<MapPageOptions> = (userOpts?: MapPageOptions) => {
  const opts = { ...defaultOptions, ...userOpts }
  
  return {
    name: "MapPage",
    getQuartzComponents() {
      return []
    },
    async emit(ctx, content, resources): Promise<FilePath[]> {
      const fps: FilePath[] = []
      const allFiles = content.map((c) => c[1].data)
      
      // Process location data
      const locationsData: MapLocation[] = allFiles
        .filter(f => f.frontmatter?.position || 
                     f.frontmatter?.coordinates || 
                     f.frontmatter?.location)
        .map(f => processLocationData(f))
      
      // Extract unique tags and topics
      const allTags = [...new Set(locationsData.flatMap(loc => loc.tags))].sort()
      const allTopics = [...new Set(locationsData.flatMap(loc => loc.topics))].sort()
      
      // Generate the HTML page
      const mapHtml = generateFullPage(
        opts.title!,
        locationsData,
        allTags,
        allTopics,
        opts.filterPresets!,
        opts.config!,
        opts.footerConfig!
      )
      
      // Write the file
      const fp = await write({
        ctx: ctx,
        slug: opts.slug!,
        ext: ".html",
        content: mapHtml,
      })
      
      fps.push(fp)
      return fps
    },
  }
}

function generateFullPage(
  title: string,
  locations: MapLocation[],
  allTags: string[],
  allTopics: string[],
  filterPresets: typeof DEFAULT_FILTER_PRESETS,
  config: typeof DEFAULT_MAP_CONFIG,
  footerConfig: typeof DEFAULT_FOOTER_CONFIG
): string {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
  ${generateHead(title)}
  <style>
    ${mapStyles}
  </style>
</head>
<body class="map-page">
  <div class="page-wrapper">
    ${generateHeader(allTopics, allTags, locations.length)}
    ${generateMapContainer()}
  </div>
  ${generateFooter(footerConfig)}
  ${generateScriptTags()}
  <script>
    ${generateMapScript(locations, filterPresets, config)}
  </script>
</body>
</html>
  `
}