# Publishing and GitHub Pages

The documentation mirrors the reference project's overview/getting-started/guides/reference/maintainers organization. MkDocs Material builds it into a static site; no Python server is needed after deployment.

## Preview locally

```console
python -m pip install -e ".[docs]"
python -m mkdocs serve
```

For a production artifact, run `python -m mkdocs build --strict`. Generated files are in `site/`, which stays out of git.

## GitHub Pages

Push this repository to GitHub, then open **Settings > Pages > Build and deployment > Source** and choose **GitHub Actions**. The `docs.yml` workflow builds the site and publishes the artifact on pushes to `main` or a manual dispatch. Pull requests build the docs without deployment. GitHub supplies the deployed URL; no guessed repository URL or custom domain is baked into the docs.

The workflow grants Pages write access only to its deployment job and uses the `github-pages` environment. Enabling Pages or publishing externally is not part of a local build.

## Package artifacts

```console
python -m build
python -m pip install dist/prydwen_py-0.1.0-py3-none-any.whl
```

The CI workflow runs tests on supported Python versions, validates lint/types/docs, and uploads wheel/source artifacts. Version metadata is in `pyproject.toml` and `prydwen.__version__`; keep both aligned. Select a project license and add its metadata before publishing a public distribution. No license or automated PyPI upload has been imposed by this implementation.
