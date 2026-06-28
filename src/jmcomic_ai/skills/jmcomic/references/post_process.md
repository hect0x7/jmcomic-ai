# Post-Process `dir_rule` Reference

Detailed `dir_rule` usage and output-path examples for `post_process`. The SKILL.md summary
points here; this file carries the full set of combinations.

## `dir_rule` Structure

The `dir_rule` parameter takes a dictionary: `{"rule": "DSL_STRING", "base_dir": "BASE_PATH"}`.

- **`Bd`**: Refers to `base_dir`.
- **`Axxx`**: Album attributes (e.g., `Aid`, `Atitle`, `Aauthor`).
- **`Pxxx`**: Photo/Chapter attributes (e.g., `Pid`, `Ptitle`, `Pindex`).
- **`{attr}`**: Python string format support for any metadata attribute.

## Examples by Process Type

### 1. ZIP Compression (`process_type="zip"`)
*   **Album Level (Single ZIP for entire manga)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Atitle}.zip", "base_dir": "D:/Comics/Archives"}}`
*   **Photo Level (Individual ZIP for each chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.zip", "base_dir": "D:/Comics/Exports"}}`

### 2. PDF Conversion (`process_type="img2pdf"`)
*   **Album Level (One PDF for all chapters combined)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Aauthor}-{Atitle}.pdf", "base_dir": "D:/Comics/PDFs"}}`
*   **Photo Level (One PDF per chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.pdf", "base_dir": "D:/Comics/Chapters"}}`

### 3. Long Image Merging (`process_type="long_img"`)
*   **Album Level (All pages combined into one huge image)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Atitle}_Full.png", "base_dir": "D:/Comics/Long"}}`
*   **Photo Level (One long image per chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.png", "base_dir": "D:/Comics/Long"}}`

> ⚠️ **Best Practice - Avoiding Overwrites**:
> When processing multiple different albums (e.g., in a loop) into the same `base_dir`, ALWAYS include unique identifiers like `{Aid}` or `{Atitle}` in your `rule`. Using a static rule like `"Bd/output.pdf"` will cause subsequent albums to overwrite previous ones.

**Workflow Suggestion**: Use `download_album` first to ensure source images exist, then call `post_process`. The tool returns the **actual predicted path** of the result.
