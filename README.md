# Google Tasks to Super Productivity Converter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool to convert Google Tasks Takeout JSON exports to Super Productivity-compatible JSON import files.

> **Note**: This project extends [GoogleTasksJSONtoTXT](https://github.com/thethales/GoogleTasksJSONtoTXT) by Thales, adding full Super Productivity import support.

## Overview

This tool allows you to migrate your tasks from Google Tasks to [Super Productivity](https://super-productivity.com/), an open-source time tracking and to-do list application. It preserves:

- All task titles and notes
- Task completion status
- Due dates
- Subtask/parent relationships
- Task list organization (converted to SP projects)

## Requirements

- Python 3.9 or higher
- No external dependencies (uses only Python standard library)

## Quick Start

```bash
# Basic conversion
python google_tasks_to_sp.py Tasks.json

# With options
python google_tasks_to_sp.py Tasks.json -o my_import.json -v
```

## Full Usage Guide

### Step 1: Export Your Google Tasks

1. Go to [Google Takeout](https://takeout.google.com/)
2. Deselect all products, then select only **"Tasks"**
3. Click "Next step" and choose your export options
4. Download the export when ready
5. Extract the ZIP file - you'll find `Tasks.json` in `Takeout/Tasks/`

### Step 2: Convert to Super Productivity Format

```bash
# Basic usage
python google_tasks_to_sp.py Tasks.json

# Specify output file
python google_tasks_to_sp.py Tasks.json -o my_tasks.json

# Verbose output (shows conversion details)
python google_tasks_to_sp.py Tasks.json -v

# Validate only (dry run - no file written)
python google_tasks_to_sp.py Tasks.json --validate

# Full example
python google_tasks_to_sp.py ~/Downloads/Takeout/Tasks/Tasks.json -o output/super_productivity_import.json -v
```

### Step 3: Import into Super Productivity

1. Open Super Productivity
2. Go to **Settings** (gear icon)
3. Navigate to **"Import/Export"** section
4. Select **"Import from file"**
5. Choose your generated JSON file
6. **Important**: You may see an error popup - this is a known SP bug. Dismiss it.
7. **Close and restart Super Productivity completely**
8. Your tasks should now be visible under their respective projects

## Command Line Options

| Option | Description |
|--------|-------------|
| `input_file` | Path to Google Tasks JSON file (required) |
| `-o, --output` | Output file path (default: `super_productivity_import.json`) |
| `-v, --verbose` | Show detailed conversion information |
| `--validate` | Validate without writing output (dry run) |

## Data Mapping

| Google Tasks | Super Productivity | Transformation |
|-------------|-------------------|----------------|
| `task.title` | `task.title` | Direct copy (empty → "Untitled Task") |
| `task.notes` | `task.notes` | Direct copy |
| `task.status` | `task.isDone` | "completed" → true |
| `task.due` | `task.dueDay` | ISO 8601 → "YYYY-MM-DD" |
| `task.completed` | `task.doneOn` | ISO 8601 → Unix ms |
| `task.updated` | `task.updated` | ISO 8601 → Unix ms |
| `task.id` | `task.id` | New UUID generated |
| `task.parent` | `task.parentId` | Mapped via ID lookup |
| `taskList.title` | `project.title` | Direct copy |
| `taskList.id` | `project.id` | New UUID generated |

## Features

- **Full Task Preservation**: Titles, notes, dates, and completion status
- **Subtask Support**: Parent-child relationships maintained
- **Unicode Support**: International characters and emoji fully supported
- **Duplicate ID Handling**: Tasks with duplicate IDs get unique UUIDs
- **Validation**: Built-in validation detects circular references and orphans
- **Dry Run Mode**: Test conversions without writing files

## Troubleshooting

### "Import failed" or error popup in Super Productivity

This is a known bug in Super Productivity's reload mechanism after import. The data is usually imported successfully despite the error.

**Solution**: Close Super Productivity completely and reopen it. Your tasks should appear.

### Tasks not appearing after import

1. Make sure you **fully restarted** Super Productivity (not just minimized)
2. Check that you imported the correct file (look at the file timestamp)
3. Look in **all projects** in the left sidebar - tasks are organized by their original Google Tasks list name

### Notes not visible

Notes are stored in SP's task detail panel. Click on the notes icon at the far right of the task to open the notes panel.

### "not a directory" error

This is an Electron/filesystem bug in SP, not related to your data. Dismiss the error, restart SP, and your data should be there.

## Running Tests

```bash
# Run all tests
python -m unittest test_conversion -v

# Run specific test class
python -m unittest test_conversion.TestTaskConversion -v
```

## Technical Details

### Output Format

The converter generates a `CompleteBackup` format compatible with Super Productivity v16.9+:

```json
{
  "timestamp": 1234567890000,
  "lastUpdate": 1234567890000,
  "crossModelVersion": 4.4,
  "data": {
    "project": { "ids": [...], "entities": {...} },
    "task": { "ids": [...], "entities": {...} },
    "tag": { "ids": [...], "entities": {...} },
    "globalConfig": {...},
    "boards": { "boardCfgs": [] },
    "note": { "ids": [], "entities": {}, "todayOrder": [] },
    ...
  }
}
```

### Compatibility

- **Tested with**: Super Productivity v16.9.4
- **Cross-model version**: 4.4 (current as of January 2026)
- **Sync support**: Works with WebDAV, Dropbox, and local file sync

### File Structure

```
Google_Tasks_to_Super_Productivity/
├── google_tasks_to_sp.py    # Main converter script
├── test_conversion.py       # Unit tests
├── Tasks_sample.json        # Sample input for testing
├── output/                  # Default output directory
│   └── super_productivity_import.json
├── README.md               # This file
└── LICENSE                 # MIT License
```

## Legacy: TXT Export

The original [GoogleTasksJSONtoTXT](https://github.com/thethales/GoogleTasksJSONtoTXT) functionality is still available:

- `run_gui.py` - GUI for TXT export
- `run_silent.py` - CLI for TXT export

---

## License

MIT License - see [LICENSE](LICENSE) for details.

## Attribution & Acknowledgments

### Original Project

This project is based on [GoogleTasksJSONtoTXT](https://github.com/thethales/GoogleTasksJSONtoTXT) by **Thales** (2020), which provided the foundation for Google Tasks JSON parsing.

### Super Productivity

Import format compatible with [Super Productivity](https://github.com/johannesjo/super-productivity) by **Johannes Millan** and contributors (MIT License). The data format was developed by analyzing Super Productivity's public source code. No Super Productivity code is included in this converter.

### Google

Google Tasks and Google Takeout are products of Google LLC.

### Development

Super Productivity converter functionality developed by **j57n-3co-x-5735** (2026) with assistance from Claude (Anthropic).

---

## Contributing

Contributions welcome! Please submit issues or pull requests.

## Disclaimer

This software is provided "as is" without warranty. The authors are not affiliated with Google LLC or the Super Productivity project. Always backup your data before importing.
