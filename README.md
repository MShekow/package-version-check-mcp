# package-version-check-mcp
A MCP server that returns the current, up-to-date version of packages you use as dependencies in a variety of ecosystems, such as Python, NPM, Go, or GitHub Actions

## Development

### Package management with Poetry

#### Setup

On a new machine, create a venv for Poetry (in path `<project-root>/.poetry`), and one for the project itself (in path `<project-root>/.venv`), e.g. via `C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe -m venv <path>`.
This separation is necessary to avoid dependency _conflicts_ between the project and Poetry.

Using the `pip` of the Poetry venv, install Poetry via `pip install -r requirements-poetry.txt`

Then, run `poetry install`, but make sure that either no venv is active, or the `.venv` one, but **not** the `.poetry` one (otherwise Poetry would stupidly install the dependencies into that one, unless you previously ran `poetry config virtualenvs.in-project true`).

#### Updating dependencies

- When dependencies changed **from the outside**, e.g. because Renovate updated the `pyproject.toml` and `poetry.lock` file, run `poetry sync` to update the local environment. This removes any obsolete dependencies from the `.venv` venv.
- If **you** updated a dependency in `pyproject.toml`, run `poetry update` to update the lock file and the local environment.
- To only update the **transitive** dependencies (keeping the ones in `pyproject.toml` the same), run `poetry update --sync`, which updates the lock file and also installs the updates into the active venv.

Make sure the `.venv` venv is active while running any of the above `poetry` commands.
