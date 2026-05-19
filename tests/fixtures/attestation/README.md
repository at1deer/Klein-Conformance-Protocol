# Attestation Fixtures

These fixtures exercise Attestation Profile v1 stub validation.

They are none/mock artifacts only:

- not TPM quotes;
- not TEE, SGX, SEV, PCR, enclave, or secure-element evidence;
- not hardware attestation proof;
- not hardware identity proof;
- not evidence of physical execution or HIL execution;
- no external hardware root or external service is involved.

Current alpha validation accepts `none` and `mock` attestation statements and rejects mock artifacts
that claim hardware attestation.
