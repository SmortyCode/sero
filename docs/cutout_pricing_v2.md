# CutoutPipelineV2 + PricingPipelineV2

Stand: 9. August 2026

## Feature-Flags

| Flag | Wirkung |
|---|---|
| `SERO_CUTOUT_V2=1` | Produktionspfad über `web.cutout_v2.run_cutout` |
| `SERO_CUTOUT_V2_SHADOW=1` | Parallel nach `tmp/cutout_shadow/`; Legacy bleibt |
| `SERO_PRICING_V2=1` | Async Preisjobs + Key v2 |
| `SERO_PRICING_V2_SHADOW=1` | Jobs/Keys parallel, Legacy-Anzeige bleibt |

Default: alle aus. Canary/Default-Umschaltung nur nach Freigabe.

## Cutout

- Öffentliche API: `run_cutout(CutoutRequest) -> CutoutResult`
- Routing: bestätigt (graded/cert) → persistiert → Geometrie → ein Vision-Fallback
- QA-Hard-Fails: opak, Canvas-Touch, Aspect, Warp/Original, leere Maske
- Speicherung: temp → QA → atomar; `.prev.png` Rollback
- BRIA-RMBG-2.0: bewusst nicht verfügbar (`non_commercial`)

## Pricing

- Canonical Identity in `web/identity.py` + Keys in `web/pricing_v2/keys.py`
- `ref_id` nur Alias, nie alleiniger Key
- Typed Provider-Results; eBay Browse = ASKING; PC = GUIDE; TCGCSV = RAW
- Jobs: QUEUED → … → COMPLETE / NO_MARKET_DATA / RETRYABLE_ERROR / PERMANENT_ERROR
- UI: kein Erfolgstoast bei Timeout; Polling derselben Job-ID

## Rollback

1. Flags aus → Legacy-Pfade
2. Cutout: `foo_cut.prev.png` zurück nach `foo_cut.png`
3. Key-Migration nur dry-run bis Freigabe

## Benötigte Entscheidungen / Keys

- Picsart / PhotoRoom Keys (optional)
- Canary-Anteil / Allowlist
- Human-approved Alpha-GTs für Gold-Fälle
