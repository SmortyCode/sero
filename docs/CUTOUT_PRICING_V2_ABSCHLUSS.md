# Abschlussbericht CutoutPipelineV2 + PricingPipelineV2

Stand: 9. August 2026

## Geänderte / neue Dateien (Kern)

- `web/cutout_v2/` — types, metrics, qa, routing, adapters, storage, pipeline, jobs
- `web/pricing_v2/` — keys, query_plan, match, merge, providers, jobs, money, types
- `scripts/cutout_baseline_metrics.py`, `scripts/eval_cutout_refs.py`, `scripts/bench_cutout_models.py`
- `scripts/migrate_identity_keys_v2.py`
- `tests/fixtures/cutout_gold/manifest.json`
- `tests/test_cutout_metrics.py`, `tests/test_pricing_identity_v2.py`
- `web/cardscan.py`, `web/app_api.py`, `bot/render.py`, `web/catalog.py`,
  `web/pricecharting.py`, `web/tcgcsv.py`
- `frontend/sero.js` (+ Pin 191), `frontend/index.html`
- `docs/cutout_pricing_v2.md`, `docs/cutout_model_benchmark.md`, dieser Bericht

## Architektur

Siehe `docs/cutout_pricing_v2.md`. Eine Cutout-API, deterministisches Typ-Routing,
Kandidaten+QA, atomare Writes. Preise: Canonical Identity + Key v2, QueryPlan,
typed Provider, persistente Jobs, monotones Cache-Merge.

## Migration

`scripts/migrate_identity_keys_v2.py --dry-run` (Default). Kein Apply ohne Freigabe.
`ref_id`-only Keys werden nicht blind übernommen.

## Baseline / Benchmark

- Baseline-Summary unter `tmp/cutout_baseline/summary.json` (73 Cuts: 24 nahezu
  opak, 34 Canvas-Touch; Anker bestätigt).
- Modelltabelle: `docs/cutout_model_benchmark.md` — Produktionsdefault bleibt
  rembg BiRefNet/IS-Net; BRIA blockiert; weitere Adapter `unavailable`.

## Tests

Zielgerichtet grün u. a.: cutout_metrics, pricing_identity_v2, catalog (4/102
xfail geschlossen), render_standard, cutout_layout, pricing, identity, PC-Gate.

## Feature-Flags / Rollback

Flags aus = Legacy. Cutout `.prev.png` restore. Key-Migration nur dry-run.

## Grenzen / offene Entscheidungen

1. Canary-Prozent / Allowlist
2. Human-approved Alpha-GTs für Gold (IoU)
3. Weights+Lizenz für HR-Matting, InSPyReNet, BEN2, SAM2+Matte
4. Optional Picsart/PhotoRoom-Keys (nie im Repo)
5. Default `SERO_CUTOUT_V2` / `SERO_PRICING_V2` erst nach Canary-Metriken
6. Slab-Matting/De-Kontamination hinter Legacy-rembg noch nicht als neues Modell

## Keine Live-eBay-Mutationen

In diesem Durchlauf keine Publish/End/Delete/Refund-Calls.
