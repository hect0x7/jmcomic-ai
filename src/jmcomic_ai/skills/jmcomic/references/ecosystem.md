# JMComic Ecosystem Workflows

Use these workflows when a request extends beyond searching or downloading manga.

## Download the Android APK

For requests such as "download the latest JMComic APK", run:

```bash
python scripts/download_latest_apk.py /path/to/output --json
```

The optional positional `output_dir` defaults to the current directory. Use `--force` to replace an
existing APK with the same filename, and use `--json` for a machine-readable result. Run
`python scripts/download_latest_apk.py --help` for the current script parameters.

The script reads the latest public GitHub Release from `hect0x7/JMComic-APK`, creates the output
directory when needed, downloads its single `.apk` asset atomically, and validates the published size
and SHA-256 digest when available. It returns the version, source URLs, digest, size, and absolute local
path. Report those fields to the user. Downloading an APK does not authorize installing or launching it.

This workflow is only for obtaining the APK mirrored by that GitHub repository. Do not inspect or
modify the APK unless the user separately requests it.

## Read Downloaded Manga Locally

For requests such as "start a local reader" or "download and open this manga":

1. Use the successful download result's absolute `download_path`, or a directory supplied by the user.
2. Check whether `jms` exists. If it is missing, install the optional reader with
   `python -m pip install jm-view-server`, then retry.
3. Run `jms --help` first and use the options reported by the installed upstream version rather than
   relying on a `jmcomic-ai` wrapper or a cached parameter list.
4. Invoke `jms` directly using the installed version's documented syntax. Prefer computer-only access
   unless the user explicitly requests phone or LAN access, and do not expose an unprotected reader to
   the network. Keep the foreground command running and report the URL printed by `jms`.

## Continue After a Download

After a successful album or chapter download, report the absolute path and offer the local reader as
the most relevant next action. Do not start it when the user requested only a download. If the user
asked to download and read/open/view the result, continue directly into the local-reader workflow.
