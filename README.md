# Python package template

This repo is a template for Python packages. It uses `poetry` for dependency management and packaging, `ruff` for formatting, `pyright` for type-checking, `pytest` for testing, and sphinx for documentation.

## Usage

1. Create a new repo using this template on GitHub by clicking the "Use this template" button at the top of the page.

1. Clone the new repo and replace the placeholders from the template with the appropriate values for your new project. All placeholders are in all caps and are delimited by square brackets. To find all of the placeholders, you can use the following command:

    ```bash
    git grep "\[[A-Z _-]\{2,\}\]"
    ```

    Alternatively, in VS Code, you can use the "Find in Files" feature with the following regex pattern: `\[([A-Z _-]{2,})\]`.

1. Follow the instructions in the `README_TEMPLATE.md` file to set up a development environment.

1. Enable the GitHub Actions workflow that runs the tests by opening `.github/workflows/test.yml` and deleting the line `if: false`.

1. Finally, delete this `README.md` file and rename the `README_TEMPLATE.md` file to `README.md`.
