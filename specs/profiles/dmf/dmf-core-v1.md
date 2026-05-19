# DMF Core Profile v1

The DMF profile family defines digital microfluidic carrier semantics, topology, addressing,
sensing expectations, operation primitives, tolerances, and failure modes. Klein Core does not
embed these details.

## Alpha Payload Formats

The reference v1 alpha supports these DMF payload forms:

- `CHANNEL_LIST`: tick-grouped channel actuation entries with explicit voltage and optional
  frequency.
- `FRAME_SEQUENCE` / `sparse`: electrode ids or declared x/y grid coordinates.
- `FRAME_SEQUENCE` / `bitmap`: strict base64 bitmap payloads bounded by declared channel count.
- `FRAME_SEQUENCE` / `delta_tiles`: stateful add/remove frame construction.
- `BITMAP_SEQUENCE`: strict base64 bitmap frames.

Frame conversion canonically sorts entries by `t` before constructing runtime frames.
`FRAME_SEQUENCE` / `rle` is not implemented in v1 alpha and is rejected with
`PAYLOAD_UNSUPPORTED_FRAME_FORMAT`. Profile validation consumes declared capabilities and topology;
the reference virtual substrate defaults are not normative board constants.
