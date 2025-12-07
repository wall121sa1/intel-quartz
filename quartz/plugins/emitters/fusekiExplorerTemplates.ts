import { generateFusekiExplorerScript } from "./fusekiExplorerScript"
import styles from "./styles/fuseki-explorer.scss"

export function buildFusekiExplorerPage(title: string, endpoint: string, baseUri: string) {
  const script = generateFusekiExplorerScript(endpoint, baseUri)
  return `
<!DOCTYPE html>
<html lang="en" class="fuseki-explorer">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title}</title>
  <style>${styles}</style>
</head>
<body class="fuseki-explorer">
  <main class="fuseki-explorer__shell">
    <header>
      <p class="fuseki-badge">Fuseki live search</p>
      <h1>${title}</h1>
      <p class="fuseki-explorer__lead">Run focused SPARQL queries against your Jena Fuseki knowledge graph, discover which reports mention people and places, and project the results on an interactive map.</p>
      <a class="fuseki-home" href="/">← Back to Quartz home</a>
    </header>

    <section class="fuseki-panel">
      <h2>Query builder</h2>
      <form id="fuseki-query-form">
        <div class="fuseki-controls__grid">
          <div class="fuseki-field">
            <label for="fuseki-endpoint">SPARQL endpoint</label>
            <input id="fuseki-endpoint" name="endpoint" type="url" placeholder="http://localhost:3030/knowledge-graph/sparql" required />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-base">Base namespace</label>
            <input id="fuseki-base" name="base" type="text" placeholder="http://myvault.com/" />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-template">Relationship focus</label>
            <select id="fuseki-template" name="template">
              <option value="mentionsByEntity">Reports that mention an entity</option>
              <option value="entityNearLocation">Reports connecting an entity to a place</option>
              <option value="relationshipHops">Reports with co-mentioned entities</option>
            </select>
          </div>
          <div class="fuseki-field">
            <label for="fuseki-entity">Entity keyword</label>
            <input id="fuseki-entity" name="entity" type="text" placeholder="Company, person, event…" required />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-place">Place keyword (optional)</label>
            <input id="fuseki-place" name="place" type="text" placeholder="City, country, facility" />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-start">Start date</label>
            <input id="fuseki-start" name="start" type="date" />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-end">End date</label>
            <input id="fuseki-end" name="end" type="date" />
          </div>
          <div class="fuseki-field">
            <label for="fuseki-limit">Result limit</label>
            <input id="fuseki-limit" name="limit" type="number" value="200" min="1" max="1000" />
          </div>
        </div>

        <div class="fuseki-actions">
          <button type="submit">Run SPARQL query</button>
          <button type="button" class="secondary" id="fuseki-preview">Refresh preview</button>
          <span class="fuseki-inline">
            <strong>Tips:</strong>
            <span class="fuseki-chip">Click the map markers to see report titles</span>
            <span class="fuseki-chip">Click "Open source" to jump to raw IRIs</span>
          </span>
        </div>
      </form>
    </section>

    <section class="fuseki-panel">
      <h2>Generated SPARQL</h2>
      <textarea id="sparql-preview" readonly></textarea>
      <p class="fuseki-footnote">The builder includes namespace prefixes for your base, RDF, RDFS, GEO, and XSD. You can copy the query directly into Fuseki's console or reuse it elsewhere.</p>
    </section>

    <section class="fuseki-panel">
      <div class="fuseki-results__meta">
        <span><strong id="fuseki-hit-count">0</strong> matches</span>
        <span id="fuseki-status" class="fuseki-results__status">Awaiting query…</span>
      </div>
      <div class="fuseki-results__grid">
        <div id="fuseki-list"></div>
        <div id="fuseki-map">
          <div class="fuseki-footnote">Map ready — run a query that returns locations to populate it.</div>
        </div>
      </div>
    </section>
  </main>
  <script>${script}</script>
</body>
</html>
  `
}
