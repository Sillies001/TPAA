# TPAA Linux release packaging

PIQB B6 generates the governed Linux Desktop and Service release packages from the exact candidate revision. Generated archives are CI artifacts and are not committed to this directory.

Required profiles:
- `LINUX_DESKTOP_X64`
- `LINUX_SERVICE_X64`

The release envelope contains an embedded runtime, PIQB build/release manifests and SPDX 2.3 SBOM. Formal release status is granted only by protected-main `TPAA_PIQB_EXIT_REVIEW_V1`.
