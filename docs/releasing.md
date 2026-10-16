# Release Procedure

Releases are deliberate, manual project events. A green CI run does not create a
tag, GitHub release or package publication automatically.

The software version and the serving-contract version are separate identities:

- software/package/FastAPI version: `0.3.0`;
- frozen role-specific serving contract: `2.0.0`.

Changing the package version does not imply a serving-schema change.

## Before tagging

Run the local engineering gates:

```bash
make lint
make test
make notebook-check
```

Generate a current role-specific serving run, then verify the locally provable
portfolio boundary:

```bash
make batch-forecast
make readiness-check
```

Verify release metadata:

```bash
make release-check
```

Also confirm that the required CI evidence workflows are green on the exact
commit intended for release:

- main CI;
- capacity-target benchmark evidence;
- staffing-decision benchmark evidence;
- hybrid-policy benchmark evidence;
- architecture render verification;
- any other workflow explicitly required by the current roadmap.

A release must not weaken the evidence boundaries in
[`ROADMAP.md`](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/blob/main/ROADMAP.md) or
[`production_readiness.md`](production_readiness.md).

## Version update contract

For a future release version `X.Y.Z`:

1. update the Poetry version in `pyproject.toml`;
2. update `clinic_forecast.__version__`;
3. ensure FastAPI still reads the package version rather than a literal;
4. update `CITATION.cff`;
5. add a matching changelog section;
6. keep `V2_CONTRACT_VERSION` unchanged unless the serving schema itself changes;
7. run `make release-check`.

## Manual tag and GitHub release

Only after the exact commit passes the release gates:

```bash
git tag -s vX.Y.Z -m "Clinic Forecasting Platform vX.Y.Z"
git push origin vX.Y.Z
```

Create the GitHub release manually from that tag and use the corresponding
changelog section as the release-note basis.

Do not describe a version as formally released merely because its metadata has
been prepared in the repository.

## Publication

This repository does not currently publish automatically to PyPI. Any future
package publication should be added as a separate, explicitly reviewed release
workflow with protected credentials and a manual approval boundary.
