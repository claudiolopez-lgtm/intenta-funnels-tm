# Intenta Funnels — Translation Memory

Approved translations used by the **Intenta Funnels Localization** Figma plugin.

## How the plugin uses this repo

For each language, the plugin loads `tm-<locale>.json` from this repo
(via `raw.githubusercontent.com`), caches it locally for 1 hour, and looks up
every text layer there before asking Claude. Strings found here are inserted
as-is (shown with ⚡ in the plugin).

## File format

One file per locale, named `tm-<locale>.json` (e.g. `tm-es.json`, `tm-de.json`),
containing a flat object of English source → approved translation:

```json
{
  "Find out your connection language": "Descubre tu lenguaje de conexión",
  "Get my results": "Ver mis resultados"
}
```

Lookups ignore case, surrounding whitespace and trailing punctuation.

## Updating

1. Edit or regenerate a `tm-<locale>.json` file (see `build_tm.py` for building from Apple Numbers TM exports)
2. Commit on `main`
3. Users get the change after their local cache expires (≤ 1 hour) or after reloading the plugin
