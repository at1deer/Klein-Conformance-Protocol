# Klein HAIL Chain Fixtures

These fixtures are implementation-independent targets for Klein HAIL chain v1
verifiers.

Algorithm:

1. Validate strict HAIL v1.
2. Exclude `RUN_END` for the pre-close chain.
3. Sort events using Klein HAIL event ordering.
4. Serialize each event with RFC 8785/JCS canonical JSON.
5. Start with `h0 = SHA256(b"KLEIN-HAIL-CHAIN-v1\0" + b"GENESIS")`.
6. For each pre-close event, compute
   `h_i = SHA256(domain + h_{i-1} + b"\0" + event_bytes_i)`.
7. The terminal digest is represented as `sha256:<hex(h_n)>`.

Fixture `lifecycle_stream.jsonl` has:

- canonical full-stream digest:
  `sha256:6f6601bf97252faf9f39247ac57603040bb700a1b893a9c1322f824c38059568`
- pre-close chain digest:
  `sha256:fd1359a9c1367425b56dd91b49695f26b10a98b427ae967bd34b555c022dec30`
