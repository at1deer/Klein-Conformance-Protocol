# OpenDrop/EWOD Dry-Run Demo

Canonical OpenDrop dry-run config:

```text
tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
```

Validate it:

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
```

Run the dry-run:

```bash
python -c "from pathlib import Path; Path('.tmp').mkdir(exist_ok=True)"
klein-opendrop-backend dry-run-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp/opendrop_dry_run
```

The OpenDrop/EWOD adapter is a dry-run/config-only skeleton. It maps KCP DMF channel concepts to
OpenDrop-style electrode intents and produces dry-run artifacts. It does not import an OpenDrop SDK,
open hardware transport, control voltages, or prove droplet motion.

Transport planning fixtures live beside this config and serialize deterministic command streams
without device IO. KCP does not copy or vendor GaudiLabs/OpenDrop firmware or controller code; future
hardware integration requires license compatibility review before copying or deriving from
GPL-licensed code.
