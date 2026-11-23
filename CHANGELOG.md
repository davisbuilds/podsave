# Changelog

## [0.2.0](https://github.com/davisbuilds/podsave/compare/v0.1.1...v0.2.0) (2026-11-23)


### ⚠ BREAKING CHANGES

* **drain:** A nonempty drain that fails every URL now exits 1. Mixed batches still exit 0. Use drain --json to check both counts.

### Bug Fixes

* **drain:** report failed batches and expose JSON counts ([b2eef26](https://github.com/davisbuilds/podsave/commit/b2eef264c204ed35c6c49a9ab738eb6a2dfc3e46))
* **queue:** require confirmation flag without a terminal ([b94afaf](https://github.com/davisbuilds/podsave/commit/b94afaf3308962fa007e8d7c56572e599c1e2956))
* **queue:** require confirmation flag without a terminal ([4a6fad5](https://github.com/davisbuilds/podsave/commit/4a6fad596a1a69390fdda6bdd460fb21031f8807))

## [0.1.1](https://github.com/davisbuilds/podsave/compare/v0.1.0...v0.1.1) (2026-10-26)


### Bug Fixes

* **deps:** upgrade certifi to 2026.10.19 for the emSign CA distrust ([eb349b6](https://github.com/davisbuilds/podsave/commit/eb349b65a8a843d3c03d72c9bd6e5017404770d3))
