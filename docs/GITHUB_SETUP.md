# Publishing safely

Commit source, tests, dependency lockfiles, documentation and the blank `.env.example` only. Local `.env` variants, demo credentials, databases, uploaded PDFs, private keys, backups, screenshots, generated outputs, dependencies and the original build prompt are excluded. Keep document-specific regression expectations in an ignored local file; `LOCAL_PDF_MANIFEST` can point browser tests at that file.

The secret scanner checks Git-selected files for common credential formats and exact known secrets from local configuration. `--staged` scans the actual index bytes. It reports filenames only. These checks reduce risk but cannot identify every possible confidential value.

Enable the repository's pre-commit protection after cloning:

```sh
git config core.hooksPath .githooks
python -m scripts.secret_scan --staged
```

Create local settings with `python -m scripts.configure`. Put your OCR key in the local `.env`; never add it to source, examples, commit messages, screenshots or repository descriptions. Existing CI checks the repository with the scanner and uses generated synthetic credentials.

Use an empty private GitHub repository initially. Add its HTTPS URL as `origin` and push `main` using Git Credential Manager or GitHub CLI authentication. Never embed a token or password in the remote URL.
