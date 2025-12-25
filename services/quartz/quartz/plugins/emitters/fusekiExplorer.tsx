import { QuartzEmitterPlugin } from "../types"
import { write } from "./helpers"
import { FilePath, FullSlug } from "../../util/path"
import { buildFusekiExplorerPage } from "./fusekiExplorerTemplates"

export interface FusekiExplorerOptions {
  title?: string
  slug?: FullSlug
  endpoint?: string
  baseUri?: string
}

const defaultOptions: Required<FusekiExplorerOptions> = {
  title: "Fuseki relationship explorer",
  slug: "fuseki-explorer" as FullSlug,
  endpoint: "http://localhost:3030/knowledge-graph/sparql",
  baseUri: "http://myvault.com/",
}

export const FusekiExplorerPage: QuartzEmitterPlugin<FusekiExplorerOptions> = (userOpts) => {
  const opts = { ...defaultOptions, ...userOpts }

  return {
    name: "FusekiExplorerPage",
    getQuartzComponents() {
      return []
    },
    async emit(ctx): Promise<FilePath[]> {
      const html = buildFusekiExplorerPage(opts.title, opts.endpoint, opts.baseUri)

      const fp = await write({
        ctx,
        slug: opts.slug,
        ext: ".html",
        content: html,
      })

      return [fp]
    },
  }
}
