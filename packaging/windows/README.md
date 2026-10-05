# TPAA Windows release packaging

PIQB B6 generates the governed Windows Desktop and Service release packages from the exact candidate revision. Generated archives are CI artifacts and are not committed to this directory.

Required profiles:
- `WINDOWS_DESKTOP_X64`
- `WINDOWS_SERVICE_X64`

The release envelope contains an embedded runtime, PIQB build/release manifests and SPDX 2.3 SBOM. Formal release status is granted only by protected-main `TPAA_PIQB_EXIT_REVIEW_V1`.
