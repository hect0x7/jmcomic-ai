# JMComic Ecosystem Workflows

Use these workflows when a request extends beyond searching or downloading manga.

## Download the Android APK

For requests such as "download the latest JMComic APK", run:

```bash
python scripts/download_latest_apk.py /path/to/output --json
```

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
3. Start a computer-only reader by default:

```bash
python scripts/start_view_server.py "/absolute/download/path"
```

The command stays in the foreground until stopped. Keep its terminal session running and give the
reported URL to the user.

For phone or LAN access, require a password and listen on all interfaces:

```bash
python scripts/start_view_server.py "/absolute/download/path" --host 0.0.0.0 --port 8080 --password "PASSWORD"
```

Replace the displayed loopback host with the computer's LAN IP when reporting a phone-access URL.
Do not expose an unprotected reader to the LAN.

## Continue After a Download

After a successful album or chapter download, report the absolute path and offer the local reader as
the most relevant next action. Do not start it when the user requested only a download. If the user
asked to download and read/open/view the result, continue directly into the local-reader workflow.
