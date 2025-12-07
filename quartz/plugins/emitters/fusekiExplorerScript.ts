export function generateFusekiExplorerScript(defaultEndpoint: string, defaultBase: string): string {
  const safeEndpoint = JSON.stringify(defaultEndpoint || "")
  const safeBase = JSON.stringify(defaultBase || "http://myvault.com/")

  return `
const leafletLoader = () => {
  if (window.L) return Promise.resolve(window.L)
  return new Promise((resolve, reject) => {
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(css)

    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => resolve(window.L)
    script.onerror = reject
    document.head.appendChild(script)
  })
}

const buildPrefixes = (base) => \`PREFIX ci: <${base}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\`

const queryTemplates = {
  mentionsByEntity: (p) => \`${'${'}buildPrefixes(p.base)${'}'}
SELECT ?report ?title ?date ?entityLabel ?placeLabel ?lat ?long
WHERE {
  ?report rdf:type ci:class/Article ;
          ci:prop/title ?title ;
          ci:prop/mentions ?entity .
  ?entity rdfs:label ?entityLabel .
  FILTER(CONTAINS(LCASE(?entityLabel), LCASE(${ '${' }JSON.stringify(p.entity)${ '}' })))
  OPTIONAL { ?report ci:prop/date ?date }
  OPTIONAL {
    ?place ci:prop/mentionedIn ?report ;
           rdfs:label ?placeLabel .
    OPTIONAL { ?place geo:lat ?lat ; geo:long ?long }
  }
  ${'${'}p.startDate || p.endDate ? \`\n  FILTER(${ '${' }buildDateFilters('date', p.startDate, p.endDate)${ '}' })\` : ''${'}'}
}
ORDER BY DESC(?date)
LIMIT ${'${'}p.limit || 200${'}'}\`,
  entityNearLocation: (p) => \`${'${'}buildPrefixes(p.base)${'}'}
SELECT ?report ?title ?date ?entityLabel ?placeLabel ?lat ?long
WHERE {
  ?report rdf:type ci:class/Article ;
          ci:prop/title ?title ;
          ci:prop/mentions ?entity .
  ?entity rdfs:label ?entityLabel .
  FILTER(CONTAINS(LCASE(?entityLabel), LCASE(${ '${' }JSON.stringify(p.entity)${ '}' })))
  ?place ci:prop/mentionedIn ?report ;
         rdfs:label ?placeLabel .
  FILTER(CONTAINS(LCASE(?placeLabel), LCASE(${ '${' }JSON.stringify(p.place)${ '}' })))
  OPTIONAL { ?place geo:lat ?lat ; geo:long ?long }
  OPTIONAL { ?report ci:prop/date ?date }
  ${'${'}p.startDate || p.endDate ? \`\n  FILTER(${ '${' }buildDateFilters('date', p.startDate, p.endDate)${ '}' })\` : ''${'}'}
}
ORDER BY DESC(?date)
LIMIT ${'${'}p.limit || 200${'}'}\`,
  relationshipHops: (p) => \`${'${'}buildPrefixes(p.base)${'}'}
SELECT DISTINCT ?report ?title ?date ?entityLabel ?linkedLabel ?placeLabel ?lat ?long
WHERE {
  ?report rdf:type ci:class/Article ;
          ci:prop/title ?title ;
          ci:prop/mentions ?entity .
  ?entity rdfs:label ?entityLabel .
  FILTER(CONTAINS(LCASE(?entityLabel), LCASE(${ '${' }JSON.stringify(p.entity)${ '}' })))

  OPTIONAL {
    ?report ci:prop/mentions ?linkedEntity .
    ?linkedEntity rdfs:label ?linkedLabel .
    FILTER(?linkedEntity != ?entity)
  }

  OPTIONAL {
    ?place ci:prop/mentionedIn ?report ;
           rdfs:label ?placeLabel .
    OPTIONAL { ?place geo:lat ?lat ; geo:long ?long }
  }

  OPTIONAL { ?report ci:prop/date ?date }
  ${'${'}p.startDate || p.endDate ? \`\n  FILTER(${ '${' }buildDateFilters('date', p.startDate, p.endDate)${ '}' })\` : ''${'}'}
}
ORDER BY DESC(?date)
LIMIT ${'${'}p.limit || 200${'}'}\`
}

const buildDateFilters = (field, start, end) => {
  const clauses = []
  if (start) clauses.push(\`?${'${'}field${'}'} >= ${'${'}JSON.stringify(start)${'}'}^^xsd:date\`)
  if (end) clauses.push(\`?${'${'}field${'}'} <= ${'${'}JSON.stringify(end)${'}'}^^xsd:date\`)
  return clauses.length ? clauses.join(' && ') : 'true'
}

const buildQuery = (form) => {
  const params = {
    endpoint: form.querySelector('#fuseki-endpoint').value.trim() || ${safeEndpoint},
    base: form.querySelector('#fuseki-base').value.trim() || ${safeBase},
    entity: form.querySelector('#fuseki-entity').value.trim(),
    place: form.querySelector('#fuseki-place').value.trim(),
    startDate: form.querySelector('#fuseki-start').value,
    endDate: form.querySelector('#fuseki-end').value,
    limit: parseInt(form.querySelector('#fuseki-limit').value, 10) || 200,
    template: form.querySelector('#fuseki-template').value
  }

  const builder = queryTemplates[params.template] || queryTemplates.mentionsByEntity
  return { query: builder(params), params }
}

const parseBindings = (bindings) =>
  bindings.map(row => ({
    report: row.report?.value || '',
    title: row.title?.value || 'Untitled report',
    date: row.date?.value || '',
    entity: row.entityLabel?.value || '',
    place: row.placeLabel?.value || '',
    linked: row.linkedLabel?.value || '',
    lat: row.lat ? parseFloat(row.lat.value) : null,
    long: row.long ? parseFloat(row.long.value) : null
  }))

const renderList = (records) => {
  const target = document.getElementById('fuseki-list')
  if (!target) return
  if (!records.length) {
    target.innerHTML = '<p class="fuseki-footnote">No matches yet. Try broadening your filters.</p>'
    return
  }

  target.innerHTML = records.map(r => \`
    <article class="fuseki-card">
      <h3 class="fuseki-card__title">${'${'}r.title${'}'}</h3>
      <div class="fuseki-card__meta">${'${'}r.entity || 'Entity unknown'${'}'}${'${'}r.place ? ' · ' + r.place : ''${'}'}${'${'}r.date ? ' · ' + r.date : ''${'}'}</div>
      <div class="fuseki-chip-row">
        ${'${'}r.linked ? \`<span class="fuseki-chip">Co-mentioned: ${'${'}r.linked${'}'}</span>\` : ''${'}'}
        ${'${'}r.report ? \`<a class="fuseki-chip" href="${'${'}r.report${'}'}" target="_blank" rel="noreferrer">Open source</a>\` : ''${'}'}
      </div>
    </article>
  \`).join('')
}

let fusekiMap
let fusekiMarkers

const renderMap = async (records) => {
  const container = document.getElementById('fuseki-map')
  if (!container) return

  const points = records.filter(r => typeof r.lat === 'number' && typeof r.long === 'number')
  if (!points.length) {
    container.innerHTML = '<div class="fuseki-footnote">No geocoded locations returned yet.</div>'
    return
  }

  const L = await leafletLoader()

  if (!fusekiMap) {
    fusekiMap = L.map('fuseki-map').setView([15, 0], 2)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(fusekiMap)
  }

  if (fusekiMarkers) {
    fusekiMarkers.clearLayers()
  } else {
    fusekiMarkers = L.layerGroup().addTo(fusekiMap)
  }

  points.forEach(p => {
    const marker = L.marker([p.lat, p.long])
    marker.bindPopup(\`
      <div class="map-popup">
        <strong>${'${'}p.title${'}'}</strong><br/>
        ${'${'}p.place || 'Unknown place'${'}'}<br/>
        ${'${'}p.date || ''${'}'}
      </div>
    \`)
    fusekiMarkers.addLayer(marker)
  })

  const bounds = L.latLngBounds(points.map(p => [p.lat, p.long]))
  fusekiMap.fitBounds(bounds.pad(0.2))
}

const setStatus = (text, isError = false) => {
  const status = document.getElementById('fuseki-status')
  if (!status) return
  status.textContent = text
  status.classList.toggle('fuseki-error', isError)
}

const initExplorer = () => {
  const form = document.getElementById('fuseki-query-form')
  const preview = document.getElementById('sparql-preview')
  if (!form || !preview) return

  form.querySelector('#fuseki-endpoint').value ||= ${safeEndpoint}
  form.querySelector('#fuseki-base').value ||= ${safeBase}

  const refreshQuery = () => {
    const { query } = buildQuery(form)
    preview.value = query
  }

  const previewButton = document.getElementById('fuseki-preview')
  if (previewButton) {
    previewButton.addEventListener('click', (e) => {
      e.preventDefault()
      refreshQuery()
      setStatus('Preview updated for current filters.')
    })
  }

  form.addEventListener('input', () => refreshQuery())

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const { query, params } = buildQuery(form)
    preview.value = query
    setStatus('Running query against Fuseki...')

    try {
      const response = await fetch(params.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/sparql-query',
          'Accept': 'application/sparql-results+json'
        },
        body: query
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(\`${'${'}response.status${'}'} ${'${'}response.statusText${'}'}: ${'${'}text.slice(0, 240)${'}'}\`)
      }

      const payload = await response.json()
      const rows = parseBindings(payload.results?.bindings || [])
      document.getElementById('fuseki-hit-count').textContent = rows.length.toString()
      renderList(rows)
      renderMap(rows)
      setStatus(rows.length ? 'Query complete.' : 'No results returned for these filters.')
    } catch (err) {
      console.error(err)
      setStatus(err?.message || 'Query failed.', true)
    }
  })

  refreshQuery()
}

document.addEventListener('nav', () => {
  initExplorer()
  if (window.addCleanup) {
    window.addCleanup(() => {
      if (fusekiMap) {
        fusekiMap.remove()
        fusekiMap = null
        fusekiMarkers = null
      }
    })
  }
})
  `
}

export default generateFusekiExplorerScript
