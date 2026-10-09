# Intenta Funnels — Glossary

Approved translations used by the **Intenta Funnels Localization** Figma plugin.

| File | Language |
| --- | --- |
| `tm-es.json` | Latin American Spanish |
| `tm-ptbr.json` | Brazilian Portuguese |

Each file maps English to the approved translation:

```json
{
  "Continue": "Continuar",
  "Get my results": "Ver mis resultados"
}
```

## How the plugin uses it

- A Figma text layer that exactly matches an entry gets that translation directly (shown with ⚡)
- Entries that appear inside longer texts are sent to Claude as required wording
- Lookups ignore case, surrounding spaces and trailing punctuation

## Updating

- **One term:** edit the JSON file here (pencil icon) and commit to `main`
- **Whole glossary:** fill `glossary-template.csv` (or any CSV/Excel/Numbers file with English + Spanish/Portuguese columns), then:
  ```bash
  python3 build_tm.py glossary-template.csv es
  python3 build_tm.py glossary-template.csv ptbr
  ```
  and upload the resulting `tm-es.json` / `tm-ptbr.json`

Changes reach plugin users within an hour, or immediately after reloading the plugin.
