# M1-WORLD-001 — Basic Episode detector

M1-WORLD-001 starts the M1-C construction wave after M1-DATA-001..007 closed.

The detector consumes only already-governed products: validated synthetic source,
authoritative Session Time, replay-stable aircraft identity, and immutable
Evaluation Context. It emits one in-memory BASIC_FLIGHT Episode per governed
fixture using half-open Session Time boundaries.

Episode identity is deterministic over the exact M1-C design inputs:
session_id, context_id, primary_aircraft_id, episode_type, start/end Session
Time, and detector version M1_BASIC_FLIGHT_EPISODE_V1. The fixture case label is
evidence metadata and is deliberately not an Episode business-identity input.

All eight governed M1 fixture cases currently share the same governed
session/context/aircraft/interval/detector identity inputs. They therefore must
resolve to the same Episode identity and logical hash while retaining distinct
fixture evidence records. The initial projection is revision 1 with no
superseded Episode. No database row is written by this task.

The governed command is:

`python tools/dev/tpaa_dev.py m1-basic-episode-check`

Windows/Linux evidence is archived at:

`evidence/m1-world-001/<platform>/basic-episode.json`

This task does not project Stage intervals, build World products, run Metrics, or
start Observation/Release logic.
