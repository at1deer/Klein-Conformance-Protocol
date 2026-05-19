# Timestamp Fixtures

These fixtures exercise Trusted Timestamp Profile v1 stub validation.

They are mock/local artifacts only:

- not RFC 3161 tokens;
- not TSA responses;
- not trusted timestamp proof;
- not evidence of physical execution or hardware attestation;
- no external authority or network access is involved.

Current alpha validation accepts `mock_local` timestamp profiles and tokens and rejects mock artifacts
that claim trusted time.
