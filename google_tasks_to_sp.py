#!/usr/bin/env python3
"""
Google Tasks to Super Productivity Converter

Converts Google Tasks Takeout JSON files to Super Productivity-compatible
JSON import files, preserving all task data and list hierarchy.

Copyright (c) 2020 Thales (GoogleTasksJSONtoTXT - original project)
Copyright (c) 2026 j57n-3co-x-5735 (Super Productivity converter)

Licensed under the MIT License. See LICENSE file for details.

Repository: https://github.com/thethales/GoogleTasksJSONtoTXT
Super Productivity: https://github.com/johannesjo/super-productivity

Usage:
    python google_tasks_to_sp.py Tasks.json
    python google_tasks_to_sp.py Tasks.json -o my_import.json --validate

Field Mappings:
    Google Tasks             Super Productivity        Transformation
    --------------------------------------------------------------------------
    task.title              task.title                Direct copy
    task.notes              task.notes                Direct copy
    task.status             task.isDone               "completed" -> true
    task.due                task.dueDay               ISO to "YYYY-MM-DD"
    task.completed          task.doneOn               ISO to Unix ms
    task.id                 task.id                   UUID generated
    task.parent             task.parentId             Map via ID mapping
    task.updated            task.updated              ISO to Unix ms
    taskList.title          project.title             Direct copy
    taskList.id             project.id                UUID generated
"""

import argparse
import json
import sys
import uuid
import warnings
from datetime import datetime
from typing import Any, Optional


# ============================================================================
# Utility Functions
# ============================================================================

def generate_uuid() -> str:
    """Generate a new UUID for entity IDs."""
    return str(uuid.uuid4())


def parse_iso_to_unix_ms(iso_string: Optional[str]) -> Optional[int]:
    """
    Convert ISO 8601 timestamp to Unix milliseconds.

    Args:
        iso_string: ISO 8601 formatted string (e.g., "2020-10-10T03:46:42.098751Z")

    Returns:
        Unix timestamp in milliseconds, or None if parsing fails
    """
    if not iso_string:
        return None

    try:
        # Handle various ISO formats
        iso_string = iso_string.replace('Z', '+00:00')

        # Try parsing with microseconds
        try:
            dt = datetime.fromisoformat(iso_string)
        except ValueError:
            # Try without microseconds
            if '.' in iso_string:
                base, frac_and_tz = iso_string.split('.')
                # Find timezone part
                if '+' in frac_and_tz:
                    frac, tz = frac_and_tz.split('+')
                    iso_string = f"{base}+{tz}"
                elif '-' in frac_and_tz:
                    parts = frac_and_tz.rsplit('-', 1)
                    if len(parts) == 2 and ':' in parts[1]:
                        iso_string = f"{base}-{parts[1]}"
                    else:
                        iso_string = base
                else:
                    iso_string = base
            dt = datetime.fromisoformat(iso_string)

        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError) as e:
        warnings.warn(f"Failed to parse timestamp '{iso_string}': {e}")
        return None


def parse_iso_to_date_string(iso_string: Optional[str]) -> Optional[str]:
    """
    Extract date string (YYYY-MM-DD) from ISO 8601 timestamp.

    Args:
        iso_string: ISO 8601 formatted string

    Returns:
        Date string in "YYYY-MM-DD" format, or None if parsing fails
    """
    if not iso_string:
        return None

    try:
        # Extract just the date part
        date_part = iso_string.split('T')[0]
        # Validate it's a proper date
        datetime.strptime(date_part, '%Y-%m-%d')
        return date_part
    except (ValueError, IndexError) as e:
        warnings.warn(f"Failed to parse date from '{iso_string}': {e}")
        return None


def sanitize_title(title: Optional[str]) -> str:
    """Ensure title is a non-empty string."""
    if not title or not title.strip():
        return "Untitled Task"
    return title.strip()


# ============================================================================
# Task Conversion
# ============================================================================

def convert_task(
    gtask: dict,
    project_id: str,
    id_mapping: dict[str, str],
    original_id_to_task: dict[str, dict]
) -> Optional[dict]:
    """
    Convert a Google Task to Super Productivity task format.

    Args:
        gtask: Google Task dictionary
        project_id: ID of the parent project
        id_mapping: Mapping from original Google Task IDs to new UUIDs
        original_id_to_task: Mapping from original IDs to task data for reference

    Returns:
        Super Productivity task dictionary, or None if task should be skipped
    """
    # Skip deleted or hidden tasks
    if gtask.get('deleted') or gtask.get('hidden'):
        return None

    original_id = gtask.get('id', '')
    task_id = id_mapping.get(original_id, generate_uuid())

    # Store mapping for subtask resolution
    if original_id:
        id_mapping[original_id] = task_id

    # Handle completion status
    is_done = gtask.get('status') == 'completed'
    done_on = None
    if is_done:
        done_on = parse_iso_to_unix_ms(gtask.get('completed'))

    # Handle timestamps
    updated_ts = parse_iso_to_unix_ms(gtask.get('updated'))
    current_ts = int(datetime.now().timestamp() * 1000)

    # Handle due date
    due_day = parse_iso_to_date_string(gtask.get('due'))

    # Handle parent reference (will be resolved in second pass)
    parent_original_id = gtask.get('parent')
    parent_id = id_mapping.get(parent_original_id) if parent_original_id else None

    return {
        "id": task_id,
        "title": sanitize_title(gtask.get('title')),
        "notes": gtask.get('notes', '') or '',
        "projectId": project_id,
        "isDone": is_done,
        "doneOn": done_on,
        "dueDay": due_day,
        "dueWithTime": None,
        "parentId": parent_id,
        "subTaskIds": [],  # Populated in second pass
        "tagIds": [],
        "timeSpent": 0,
        "timeEstimate": 0,
        "timeSpentOnDay": {},
        "created": updated_ts or current_ts,
        "updated": updated_ts or current_ts,
        "attachments": [],
        # Store original ID for debugging/reference
        "_originalGoogleTaskId": original_id if original_id else None,
    }


def convert_task_with_assigned_id(
    gtask: dict,
    project_id: str,
    assigned_id: str,
    id_mapping: dict[str, str]
) -> Optional[dict]:
    """
    Convert a Google Task to Super Productivity task format with a pre-assigned ID.

    This variant is used when handling duplicate original IDs - each task gets
    a unique assigned_id regardless of whether its original ID was seen before.

    Args:
        gtask: Google Task dictionary
        project_id: ID of the parent project
        assigned_id: Pre-assigned unique ID for this task
        id_mapping: Mapping from original Google Task IDs to new UUIDs (for parent lookup)

    Returns:
        Super Productivity task dictionary, or None if task should be skipped
    """
    # Skip deleted or hidden tasks
    if gtask.get('deleted') or gtask.get('hidden'):
        return None

    original_id = gtask.get('id', '')

    # Handle completion status
    is_done = gtask.get('status') == 'completed'
    done_on = parse_iso_to_unix_ms(gtask.get('completed')) if is_done else None

    # Handle timestamps
    updated_ts = parse_iso_to_unix_ms(gtask.get('updated'))
    current_ts = int(datetime.now().timestamp() * 1000)

    # Handle due date
    due_day = parse_iso_to_date_string(gtask.get('due'))

    # Handle parent reference (will be resolved in second pass)
    parent_original_id = gtask.get('parent')
    parent_id = id_mapping.get(parent_original_id) if parent_original_id else None

    task = {
        "id": assigned_id,
        "title": sanitize_title(gtask.get('title')),
        "notes": gtask.get('notes', '') or '',
        "projectId": project_id,
        "isDone": is_done,
        "subTaskIds": [],  # Populated in second pass
        "tagIds": [],
        "timeSpent": 0,
        "timeEstimate": 0,
        "timeSpentOnDay": {},
        "created": updated_ts or current_ts,
        "updated": updated_ts or current_ts,
        "attachments": [],
    }

    # Only include optional fields if they have values (SP expects undefined, not null)
    if done_on is not None:
        task["doneOn"] = done_on
    if due_day is not None:
        task["dueDay"] = due_day
    if parent_id is not None:
        task["parentId"] = parent_id
    if original_id:
        task["_originalGoogleTaskId"] = original_id

    return task


def build_subtask_relationships(
    tasks: dict[str, dict],
    id_mapping: dict[str, str],
    task_id_to_original: dict[str, dict]
) -> set[str]:
    """
    Second pass: Build parent-child relationships.

    Args:
        tasks: Dictionary of task_id -> task data
        id_mapping: Mapping from original IDs to new IDs (first occurrence only)
        task_id_to_original: Mapping from new task IDs to original gtask data

    Returns:
        Set of task IDs that are subtasks (have a parent)
    """
    subtask_ids = set()

    for task_id, gtask in task_id_to_original.items():
        parent_original_id = gtask.get('parent')
        if not parent_original_id:
            continue

        if task_id not in tasks:
            continue

        parent_new_id = id_mapping.get(parent_original_id)

        if parent_new_id and parent_new_id in tasks:
            # Set parent reference on child
            tasks[task_id]['parentId'] = parent_new_id
            # Add child to parent's subTaskIds
            if task_id not in tasks[parent_new_id]['subTaskIds']:
                tasks[parent_new_id]['subTaskIds'].append(task_id)
            subtask_ids.add(task_id)

    return subtask_ids


# ============================================================================
# Project Conversion
# ============================================================================

def convert_task_list(
    task_list: dict,
    all_tasks: dict[str, dict],
    id_mapping: dict[str, str],
    task_id_to_original: dict[str, dict]
) -> tuple[dict, list[str]]:
    """
    Convert a Google Tasks list to Super Productivity project.

    Args:
        task_list: Google Tasks list dictionary
        all_tasks: Dictionary to accumulate all tasks
        id_mapping: ID mapping dictionary (original_id -> first new_id, for parent lookup)
        task_id_to_original: Mapping from new task IDs to original gtask data (for subtask processing)

    Returns:
        Tuple of (project dict, list of task IDs in this project)
    """
    project_id = generate_uuid()
    task_ids = []

    # Process tasks in this list
    items = task_list.get('items', [])

    # Assign unique IDs to all tasks, handling duplicates
    # For parent lookup, only store first occurrence of each original_id
    for gtask in items:
        original_id = gtask.get('id', '')

        # Generate a unique ID for this task (always unique)
        new_id = generate_uuid()

        # Only store first occurrence in id_mapping (for parent reference resolution)
        if original_id and original_id not in id_mapping:
            id_mapping[original_id] = new_id

        # Convert task with assigned ID
        task = convert_task_with_assigned_id(gtask, project_id, new_id, id_mapping)
        if task:
            all_tasks[task['id']] = task
            task_ids.append(task['id'])
            # Store mapping for subtask processing
            task_id_to_original[task['id']] = gtask

    # Create project
    project = {
        "id": project_id,
        "title": sanitize_title(task_list.get('title')),
        "taskIds": task_ids,  # Will be filtered to remove subtasks
        "backlogTaskIds": [],
        "noteIds": [],
        "theme": {
            "primary": "#4285f4",  # Google blue
            "isAutoContrast": True,
        },
        "isArchived": False,
        "isEnableBacklog": False,
        "isHiddenFromMenu": False,
        "icon": None,
        "advancedCfg": {
            "worklogExportSettings": {
                "cols": ["DATE", "START", "END", "TIME_CLOCK", "TITLES_INCLUDING_SUB"],
                "roundWorkTimeTo": None,
                "roundStartTimeTo": None,
                "roundEndTimeTo": None,
                "separateTasksBy": "\n",
                "groupBy": "DATE",
            }
        },
    }

    return project, task_ids


# ============================================================================
# Full Conversion
# ============================================================================

def create_empty_sp_data() -> dict:
    """
    Create an empty Super Productivity data structure with defaults.

    Returns data in CompleteBackup format:
    {
        timestamp: number,
        lastUpdate: number,
        crossModelVersion: number,
        data: { ...all model data... }
    }
    """
    current_ts = int(datetime.now().timestamp() * 1000)

    # Initial time tracking state
    initial_time_tracking = {
        "project": {},
        "tag": {},
    }

    # Initial archive model structure
    initial_archive = {
        "task": {"ids": [], "entities": {}},
        "timeTracking": initial_time_tracking.copy(),
        "lastTimeTrackingFlush": 0,
    }

    # Inner data structure (AppDataCompleteNew)
    data = {
        "project": {
            "ids": [],
            "entities": {},
        },
        "task": {
            "ids": [],
            "entities": {},
            "currentTaskId": None,
            "selectedTaskId": None,
            "taskDetailTargetPanel": None,
            "lastCurrentTaskId": None,
            "isDataLoaded": True,
        },
        "tag": {
            "ids": [],
            "entities": {},
        },
        "globalConfig": create_default_global_config(),
        "reminders": [],
        "planner": {"days": {}},
        "boards": {"boardCfgs": []},
        "note": {"ids": [], "entities": {}, "todayOrder": []},
        "issueProvider": {"ids": [], "entities": {}},
        "metric": {"ids": [], "entities": {}},
        "improvement": {"ids": [], "entities": {}, "hiddenImprovementBannerItems": []},
        "obstruction": {"ids": [], "entities": {}},
        "simpleCounter": {"ids": [], "entities": {}},
        "taskRepeatCfg": {"ids": [], "entities": {}},
        "menuTree": {"projectTree": [], "tagTree": []},
        "timeTracking": initial_time_tracking,
        # Archive models with correct names
        "archiveYoung": initial_archive.copy(),
        "archiveOld": {
            "task": {"ids": [], "entities": {}},
            "timeTracking": initial_time_tracking.copy(),
            "lastTimeTrackingFlush": 0,
        },
        # Plugin models (must be arrays, not None)
        "pluginUserData": [],
        "pluginMetadata": [],
    }

    # Wrap in CompleteBackup format
    return {
        "timestamp": current_ts,
        "lastUpdate": current_ts,
        "crossModelVersion": 4.4,
        "data": data,
    }


def create_default_global_config() -> dict:
    """Create default global configuration for Super Productivity."""
    minute = 60 * 1000

    return {
        "appFeatures": {
            "isTimeTrackingEnabled": True,
            "isFocusModeEnabled": True,
            "isSchedulerEnabled": True,
            "isPlannerEnabled": True,
            "isBoardsEnabled": True,
            "isScheduleDayPanelEnabled": True,
            "isIssuesPanelEnabled": True,
            "isProjectNotesEnabled": True,
            "isSyncIconEnabled": True,
            "isDonatePageEnabled": True,
            "isEnableUserProfiles": False,
        },
        "localization": {
            "lng": None,
            "dateTimeLocale": None,
            "firstDayOfWeek": None,
        },
        "misc": {
            "isConfirmBeforeExit": False,
            "isConfirmBeforeExitWithoutFinishDay": True,
            "isConfirmBeforeTaskDelete": True,
            "isAutMarkParentAsDone": False,
            "isTurnOffMarkdown": False,
            "isAutoAddWorkedOnToToday": True,
            "isMinimizeToTray": False,
            "isTrayShowCurrentTask": True,
            "isTrayShowCurrentCountdown": True,
            "defaultProjectId": None,
            "startOfNextDay": 0,
            "isDisableAnimations": False,
            "isDisableCelebration": False,
            "isShowProductivityTipLonger": False,
            "taskNotesTpl": "**How can I best achieve it now?**\n\n**What do I want?**\n\n**Why do I want it?**\n",
            "isOverlayIndicatorEnabled": False,
            "customTheme": "default",
            "defaultStartPage": 0,
        },
        "shortSyntax": {
            "isEnableProject": True,
            "isEnableDue": True,
            "isEnableTag": True,
        },
        "evaluation": {
            "isHideEvaluationSheet": False,
        },
        "idle": {
            "isOnlyOpenIdleWhenCurrentTask": False,
            "isEnableIdleTimeTracking": True,
            "minIdleTime": 5 * minute,
        },
        "takeABreak": {
            "isTakeABreakEnabled": True,
            "isLockScreen": False,
            "isTimedFullScreenBlocker": False,
            "timedFullScreenBlockerDuration": 8000,
            "isFocusWindow": False,
            "takeABreakMessage": "You have been working for ${duration} without one. Go away from the computer! Take a short walk! Makes you more productive in the long run!",
            "takeABreakMinWorkingTime": 60 * minute,
            "takeABreakSnoozeTime": 15 * minute,
            "motivationalImgs": [],
        },
        "dominaMode": {
            "isEnabled": False,
            "interval": 5 * minute,
            "volume": 75,
            "text": "Your current task is: ${currentTaskTitle}",
            "voice": None,
        },
        "focusMode": {
            "isSkipPreparation": False,
            "isPlayTick": False,
            "isPauseTrackingDuringBreak": False,
            "isSyncSessionWithTracking": False,
            "isStartInBackground": False,
        },
        "pomodoro": {
            "duration": 25 * minute,
            "breakDuration": 5 * minute,
            "longerBreakDuration": 15 * minute,
            "cyclesBeforeLongerBreak": 4,
        },
        "keyboard": {
            "globalShowHide": "Ctrl+Shift+X",
            "globalToggleTaskStart": None,
            "globalAddNote": None,
            "globalAddTask": None,
            "addNewTask": "Shift+A",
            "addNewProject": "Shift+P",
            "addNewNote": "N",
            "openProjectNotes": "Shift+N",
            "toggleTaskViewCustomizerPanel": "C",
            "toggleIssuePanel": "P",
            "focusSideNav": "Shift+D",
            "showHelp": "?",
            "showSearchBar": "Shift+F",
            "toggleBacklog": "B",
            "goToFocusMode": "F",
            "goToWorkView": "W",
            "goToScheduledView": "Shift+S",
            "goToTimeline": "Shift+T",
            "goToSettings": None,
            "zoomIn": "Ctrl++",
            "zoomOut": "Ctrl+-",
            "zoomDefault": "Ctrl+0",
            "saveNote": "Ctrl+S",
            "triggerSync": "Ctrl+S",
            "taskEditTitle": None,
            "taskToggleDetailPanelOpen": "I",
            "taskOpenEstimationDialog": "T",
            "taskSchedule": "S",
            "taskToggleDone": "D",
            "taskAddSubTask": "A",
            "taskAddAttachment": "L",
            "taskDelete": "Backspace",
            "taskMoveToProject": "E",
            "taskOpenContextMenu": "Q",
            "selectPreviousTask": "K",
            "selectNextTask": "J",
            "moveTaskUp": "Ctrl+Shift+ArrowUp",
            "moveTaskDown": "Ctrl+Shift+ArrowDown",
            "moveTaskToTop": "Ctrl+Alt+ArrowUp",
            "moveTaskToBottom": "Ctrl+Alt+ArrowDown",
            "moveToBacklog": "Shift+B",
            "moveToTodaysTasks": "Shift+T",
            "expandSubTasks": None,
            "collapseSubTasks": None,
            "togglePlay": "Y",
            "taskEditTags": "G",
        },
        "localBackup": {
            "isEnabled": True,
        },
        "sound": {
            "volume": 75,
            "isIncreaseDoneSoundPitch": True,
            "doneSound": "ding-small-bell.mp3",
            "breakReminderSound": None,
            "trackTimeSound": None,
        },
        "timeTracking": {
            "trackingInterval": 1000,
            "defaultEstimate": 0,
            "defaultEstimateSubTasks": 0,
            "isNotifyWhenTimeEstimateExceeded": True,
            "isAutoStartNextTask": False,
            "isTrackingReminderEnabled": False,
            "isTrackingReminderShowOnMobile": False,
            "trackingReminderMinTime": 5 * minute,
            "isTrackingReminderNotify": False,
            "isTrackingReminderFocusWindow": False,
        },
        "reminder": {
            "isCountdownBannerEnabled": True,
            "countdownDuration": minute * 10,
            "defaultTaskRemindOption": "AtStart",
            "isFocusWindow": False,
        },
        "schedule": {
            "isWorkStartEndEnabled": True,
            "workStart": "9:00",
            "workEnd": "17:00",
            "isLunchBreakEnabled": False,
            "lunchBreakStart": "13:00",
            "lunchBreakEnd": "14:00",
        },
        "sync": {
            "isEnabled": False,
            "isCompressionEnabled": False,
            "isEncryptionEnabled": False,
            "encryptKey": None,
            "syncProvider": None,
            "syncInterval": minute,
            "webDav": {
                "baseUrl": None,
                "userName": None,
                "password": None,
                "syncFolderPath": "super-productivity",
            },
            "localFileSync": {
                "syncFolderPath": "",
            },
        },
    }


def convert_google_tasks_to_sp(google_tasks_data: dict, verbose: bool = False) -> dict:
    """
    Convert Google Tasks export to Super Productivity format.

    Args:
        google_tasks_data: Parsed Google Tasks JSON data
        verbose: Print detailed conversion info

    Returns:
        Super Productivity compatible data structure in CompleteBackup format:
        {timestamp, lastUpdate, crossModelVersion, data: {...}}
    """
    sp_backup = create_empty_sp_data()
    # Access the inner data structure
    sp_data = sp_backup['data']

    id_mapping: dict[str, str] = {}
    all_tasks: dict[str, dict] = {}
    task_id_to_original: dict[str, dict] = {}  # new_task_id -> original gtask
    project_task_ids: dict[str, list[str]] = {}  # project_id -> [task_ids]

    # Validate input structure
    if google_tasks_data.get('kind') != 'tasks#taskLists':
        warnings.warn("Input doesn't appear to be a Google Tasks export (missing 'kind': 'tasks#taskLists')")

    task_lists = google_tasks_data.get('items', [])

    if verbose:
        print(f"Found {len(task_lists)} task list(s)")

    # First pass: Convert all task lists and tasks
    for task_list in task_lists:
        project, task_ids = convert_task_list(task_list, all_tasks, id_mapping, task_id_to_original)
        project_task_ids[project['id']] = task_ids.copy()

        # Add project to SP data
        sp_data['project']['ids'].append(project['id'])
        sp_data['project']['entities'][project['id']] = project

        if verbose:
            list_title = task_list.get('title', 'Unknown')
            task_count = len(task_ids)
            print(f"  - '{list_title}': {task_count} task(s)")

    # Second pass: Build subtask relationships
    subtask_ids = build_subtask_relationships(all_tasks, id_mapping, task_id_to_original)

    if verbose and subtask_ids:
        print(f"Found {len(subtask_ids)} subtask(s)")

    # Remove subtasks from project taskIds (only top-level tasks should be listed)
    for project_id, task_ids in project_task_ids.items():
        top_level_task_ids = [tid for tid in task_ids if tid not in subtask_ids]
        sp_data['project']['entities'][project_id]['taskIds'] = top_level_task_ids

    # Add all tasks to SP data
    for task_id, task in all_tasks.items():
        sp_data['task']['ids'].append(task_id)
        sp_data['task']['entities'][task_id] = task

    if verbose:
        total_tasks = len(all_tasks)
        completed = sum(1 for t in all_tasks.values() if t['isDone'])
        print(f"Total tasks converted: {total_tasks} ({completed} completed)")

    return sp_backup


# ============================================================================
# Validation
# ============================================================================

def validate_sp_data(sp_backup: dict) -> list[str]:
    """
    Validate Super Productivity data structure.

    Args:
        sp_backup: Super Productivity backup data (CompleteBackup format)

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check backup wrapper structure
    if 'data' not in sp_backup:
        errors.append("Missing 'data' field in backup")
        return errors
    if 'crossModelVersion' not in sp_backup:
        errors.append("Missing 'crossModelVersion' field in backup")
    if 'timestamp' not in sp_backup:
        errors.append("Missing 'timestamp' field in backup")
    if 'lastUpdate' not in sp_backup:
        errors.append("Missing 'lastUpdate' field in backup")

    sp_data = sp_backup['data']

    # Check task ID uniqueness
    task_ids = sp_data['task']['ids']
    if len(task_ids) != len(set(task_ids)):
        errors.append("Duplicate task IDs found")

    task_entities = sp_data['task']['entities']
    project_entities = sp_data['project']['entities']

    # Check all task IDs have entities
    for task_id in task_ids:
        if task_id not in task_entities:
            errors.append(f"Task ID '{task_id}' in ids list but not in entities")

    # Check project references
    for task_id, task in task_entities.items():
        project_id = task.get('projectId')
        if project_id and project_id not in project_entities:
            errors.append(f"Task '{task_id}' references non-existent project '{project_id}'")

    # Check parent references and circular dependencies
    for task_id, task in task_entities.items():
        parent_id = task.get('parentId')
        if parent_id:
            if parent_id not in task_entities:
                errors.append(f"Task '{task_id}' references non-existent parent '{parent_id}'")
            elif parent_id == task_id:
                errors.append(f"Task '{task_id}' is its own parent (circular reference)")
            else:
                # Check for indirect circular references
                visited = {task_id}
                current = parent_id
                while current:
                    if current in visited:
                        errors.append(f"Circular parent reference detected involving task '{task_id}'")
                        break
                    visited.add(current)
                    current = task_entities.get(current, {}).get('parentId')

    # Check subTaskIds consistency
    for task_id, task in task_entities.items():
        for subtask_id in task.get('subTaskIds', []):
            if subtask_id not in task_entities:
                errors.append(f"Task '{task_id}' lists non-existent subtask '{subtask_id}'")
            else:
                subtask = task_entities[subtask_id]
                if subtask.get('parentId') != task_id:
                    errors.append(f"Subtask '{subtask_id}' doesn't reference parent '{task_id}'")

    # Check project taskIds
    for project_id, project in project_entities.items():
        for task_id in project.get('taskIds', []):
            if task_id not in task_entities:
                errors.append(f"Project '{project_id}' lists non-existent task '{task_id}'")
            else:
                task = task_entities[task_id]
                if task.get('parentId'):
                    errors.append(f"Project '{project_id}' lists subtask '{task_id}' (should only list top-level tasks)")

    return errors


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Convert Google Tasks Takeout JSON to Super Productivity import format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python google_tasks_to_sp.py Tasks.json
  python google_tasks_to_sp.py Tasks.json -o my_import.json --validate
  python google_tasks_to_sp.py Tasks.json --dry-run --verbose
        """
    )

    parser.add_argument(
        'input_file',
        help="Path to Google Tasks JSON file (from Google Takeout)"
    )

    parser.add_argument(
        '-o', '--output',
        default='super_productivity_import.json',
        help="Output file path (default: super_productivity_import.json)"
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help="Validate output against Super Productivity schema"
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Parse and validate without writing output"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Show detailed conversion information"
    )

    args = parser.parse_args()

    # Read input file
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            google_tasks_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Reading from: {args.input_file}")

    # Convert data
    try:
        sp_data = convert_google_tasks_to_sp(google_tasks_data, verbose=args.verbose)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate if requested
    if args.validate:
        if args.verbose:
            print("\nValidating output...")

        errors = validate_sp_data(sp_data)
        if errors:
            print("Validation errors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)
        elif args.verbose:
            print("Validation passed!")

    # Write output (unless dry-run)
    if not args.dry_run:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(sp_data, f, indent=2, ensure_ascii=False)

            if args.verbose:
                print(f"\nOutput written to: {args.output}")
            else:
                print(f"Converted successfully: {args.output}")

        except IOError as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.verbose:
            print("\nDry run complete - no output file written")
        else:
            print("Dry run complete")

    # Print summary (access inner data structure)
    inner_data = sp_data['data']
    task_count = len(inner_data['task']['ids'])
    project_count = len(inner_data['project']['ids'])
    print(f"Converted {task_count} task(s) in {project_count} project(s)")


if __name__ == '__main__':
    main()
