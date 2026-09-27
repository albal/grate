# grate

List Gemini API models sorted by requests-per-day (RPD), with the highest limits last.

The model list comes from the Gemini API (`models.list`). The daily limits come from your own project's quotas through the Cloud Quotas API, so the numbers reflect your project rather than published defaults.

## Requirements

- A Google Cloud project with the Cloud Quotas API enabled:

  ```sh
  gcloud services enable cloudquotas.googleapis.com --project <project-id>
  ```

- Application Default Credentials:

  ```sh
  gcloud auth application-default login
  ```

- Optionally, a `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) for listing models. Without one, the script lists models with your ADC token, which needs the `generative-language.retriever` scope.

## Usage

### With Docker

`run.sh` builds the image and runs it with your ADC credentials mounted read-only. It shows free-tier limits by default:

```sh
./run.sh [project-id] [extra options]
```

If no project ID is given, it uses `GOOGLE_CLOUD_PROJECT` or your gcloud default project.

### Directly

```sh
pip install requests google-auth
python gemini_rpd.py --project <project-id> [--tier free|paid|all] [--all-models]
```

| Option | Description |
| --- | --- |
| `--project` | GCP project ID. Defaults to `GOOGLE_CLOUD_PROJECT` or the ADC project. |
| `--tier` | `free`, `paid` or `all` (default `all`). |
| `--all-models` | Include models that don't support `generateContent`. |
| `--dump-quotas` | Print the project's raw daily quotas and exit. Useful for checking which quotas are counted as RPD. |

## Example output

```
      RPD  MODEL                  DISPLAY NAME
---------  ---------------------  ----------------------
      n/a  some-model             Some Model
      250  gemini-2.5-pro         Gemini 2.5 Pro
    1,000  gemini-2.5-flash       Gemini 2.5 Flash
```

## License

[MIT](LICENSE)
