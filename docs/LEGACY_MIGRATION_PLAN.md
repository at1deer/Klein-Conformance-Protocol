# Legacy Vector Migration Plan

The legacy 120-vector corpus is migration material, not authoritative Klein Core v1 conformance.
Do not make it green by loosening the v1 harness. Migrate vectors in small batches with explicit
`vector.json`, declared inputs, expected error codes, and strict HAIL evidence.

## Batches

1. Already covered by v1:
   `001`, `004`, `005`, `011`, `013`, `014`, `017`, `032`, `033`, `038`, `042`,
   `043`, `052`, `106`, `108`, `113`, `114`.
2. DMF payload validation candidates:
   `006`, `007`, `008`, `010`, `012`, `013`, `014`, `015`, `016`, `031`, `034`, `038`,
   `052`, `053`, `063`, `104`, `105`, `106`, `107`, `112`.
3. HAIL/observables candidates:
   `044`, `045`, `054`, `055`, `064`, `072`, `073`, `074`, `075`, `097`, `100`, `108`,
   `120`.
4. Trace/runbook candidates:
   `003`, `020`, `029`, `046`, `076`, `083`, `084`, `085`, `091`, `092`, `093`, `094`,
   `101`, `102`, `103`, `111`.
5. Capability/skip candidates:
   `018`, `022`, `024`, `025`, `026`, `027`, `040`, `065`, `116`.
6. Legacy-only terminology candidates:
   `021`, `022`, `113`, `114`, `119`.
7. Defer until real recovery/sensing exists:
   vectors that require physical observation comparison, autonomous recovery success, or
   hardware-in-loop behavior beyond the current virtual substrate.

## Next Highest-Value Migration Batch

Migrate these next, in this order:

- `010_tft_delta_invalid_remove_negative`
- `012_tft_sparse_noncanonical_order_negative`
- `012_tft_sparse_noncanonical_order_negative`
- `015_muxed_channel_list_nonmonotonic_ticks_negative`
- `031_channel_conflicting_state_negative`
- `034_tft_sparse_oob_tile_negative`
- `053_bitmap_length_mismatch_negative`
- `063_bitmap_padding_nonzero_negative`
- `104_delta_duplicate_pixel_in_remove_negative`
- `107_delta_empty_tiles_list_negative`

Each migration should decide whether the legacy expectation is still valid v1 behavior, a renamed
canonical v1 error, or an intentionally unsupported alpha feature.

Latest migrated batch:

- `013_tft_sparse_duplicate_pixels_negative` -> `N016_sparse_duplicate_pixels`
- `014_tft_rle_length_mismatch_negative` -> `N015_rle_frame_format_unsupported`
- `038_delta_add_remove_conflict_negative` -> `N017_delta_add_remove_conflict`
- `052_bitmap_unsupported_dims_negative` -> `N019_bitmap_unsupported_dimensions`
- `106_delta_remove_nonexistent_pixel_negative` -> `N018_delta_remove_inactive_pixel`
- `108_observables_mixed_kinds_order_positive` -> `009_hail_mixed_kind_order`

## DMF Profile Coverage Now Represented In v1

The authoritative v1 suite now covers the current DMF/EWOD alpha profile surface:

- `CHANNEL_LIST`: `006_channel_list_two_ticks`, `015_channel_list_multi_tick_unsorted`, and
  negatives `N006`, `N007`, `N008`, `N009`, `N010`, `N026`.
- `FRAME_SEQUENCE` / `sparse`: `007_frame_sequence_sparse`, `016_frame_sequence_sparse_coordinates`,
  and negatives `N011`, `N016`, `N027`.
- `FRAME_SEQUENCE` / `delta_tiles`: `014_frame_sequence_delta_tiles` and negatives `N017`, `N018`.
- `FRAME_SEQUENCE` / `rle`: intentionally rejected by `N015`; rle is not a v1 alpha supported format.
- `BITMAP_SEQUENCE`: `008_bitmap_sequence_minimal` and negatives `N012`, `N019`.

Deferred legacy behaviors remain migration material when they require noncanonical tick policy,
padding-bit semantics, observation truth, closed-loop recovery, HIL, or hardware-backed evidence.
Do not make the legacy namespace green by weakening v1 profile rules.
