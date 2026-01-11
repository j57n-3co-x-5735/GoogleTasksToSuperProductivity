# Output Directory

This directory contains generated Super Productivity import files.

## Default Output

When running the converter without specifying an output path, files are saved here:

```bash
python google_tasks_to_sp.py Tasks.json
# Creates: output/super_productivity_import.json
```

## Importing to Super Productivity

1. Open Super Productivity
2. Go to Settings → Import/Export
3. Select "Import from file"
4. Choose `super_productivity_import.json` from this folder
5. Dismiss any error popup (known SP bug)
6. Restart Super Productivity

Your tasks should now be visible.
