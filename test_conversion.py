#!/usr/bin/env python3
"""
Unit tests for Google Tasks to Super Productivity converter.

Run with: python -m pytest test_conversion.py -v
Or simply: python test_conversion.py
"""

import json
import unittest
from datetime import datetime

from google_tasks_to_sp import (
    convert_google_tasks_to_sp,
    convert_task,
    generate_uuid,
    parse_iso_to_date_string,
    parse_iso_to_unix_ms,
    sanitize_title,
    validate_sp_data,
)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_generate_uuid(self):
        """UUIDs should be unique."""
        uuids = [generate_uuid() for _ in range(100)]
        self.assertEqual(len(uuids), len(set(uuids)))

    def test_parse_iso_to_unix_ms_valid(self):
        """Valid ISO timestamps should parse correctly."""
        # Standard ISO format with Z
        result = parse_iso_to_unix_ms("2020-10-10T03:46:42.098751Z")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_parse_iso_to_unix_ms_simple(self):
        """Simple ISO format should work."""
        result = parse_iso_to_unix_ms("2020-10-10T03:00:00Z")
        self.assertIsNotNone(result)

    def test_parse_iso_to_unix_ms_none(self):
        """None input should return None."""
        self.assertIsNone(parse_iso_to_unix_ms(None))

    def test_parse_iso_to_unix_ms_empty(self):
        """Empty string should return None."""
        self.assertIsNone(parse_iso_to_unix_ms(""))

    def test_parse_iso_to_date_string_valid(self):
        """Valid ISO timestamps should extract date."""
        result = parse_iso_to_date_string("2020-10-10T03:46:42.098751Z")
        self.assertEqual(result, "2020-10-10")

    def test_parse_iso_to_date_string_none(self):
        """None input should return None."""
        self.assertIsNone(parse_iso_to_date_string(None))

    def test_sanitize_title_normal(self):
        """Normal titles should pass through."""
        self.assertEqual(sanitize_title("My Task"), "My Task")

    def test_sanitize_title_empty(self):
        """Empty titles should become 'Untitled Task'."""
        self.assertEqual(sanitize_title(""), "Untitled Task")
        self.assertEqual(sanitize_title(None), "Untitled Task")
        self.assertEqual(sanitize_title("   "), "Untitled Task")

    def test_sanitize_title_whitespace(self):
        """Titles with extra whitespace should be trimmed."""
        self.assertEqual(sanitize_title("  My Task  "), "My Task")


class TestTaskConversion(unittest.TestCase):
    """Test individual task conversion."""

    def test_convert_basic_task(self):
        """Basic task should convert correctly."""
        gtask = {
            "id": "task123",
            "title": "Test Task",
            "status": "needsAction",
            "updated": "2020-10-10T03:46:42.098751Z",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Test Task")
        self.assertEqual(task["projectId"], "project1")
        self.assertFalse(task["isDone"])
        self.assertIsNone(task["doneOn"])

    def test_convert_completed_task(self):
        """Completed task should have isDone=True and doneOn set."""
        gtask = {
            "id": "task123",
            "title": "Done Task",
            "status": "completed",
            "completed": "2020-10-15T10:00:00Z",
            "updated": "2020-10-10T03:46:42.098751Z",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertTrue(task["isDone"])
        self.assertIsNotNone(task["doneOn"])

    def test_convert_task_with_due_date(self):
        """Task with due date should have dueDay set."""
        gtask = {
            "id": "task123",
            "title": "Task with Due",
            "due": "2020-10-10T03:00:00Z",
            "status": "needsAction",
            "updated": "2020-10-10T03:46:42.098751Z",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertEqual(task["dueDay"], "2020-10-10")

    def test_convert_task_with_notes(self):
        """Task with notes should preserve them."""
        gtask = {
            "id": "task123",
            "title": "Task with Notes",
            "notes": "These are my notes",
            "status": "needsAction",
            "updated": "2020-10-10T03:46:42.098751Z",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertEqual(task["notes"], "These are my notes")

    def test_skip_deleted_task(self):
        """Deleted tasks should be skipped."""
        gtask = {
            "id": "task123",
            "title": "Deleted Task",
            "deleted": True,
            "status": "needsAction",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertIsNone(task)

    def test_skip_hidden_task(self):
        """Hidden tasks should be skipped."""
        gtask = {
            "id": "task123",
            "title": "Hidden Task",
            "hidden": True,
            "status": "needsAction",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertIsNone(task)

    def test_task_id_mapping(self):
        """Task conversion should update ID mapping."""
        gtask = {
            "id": "original_id_123",
            "title": "Test Task",
            "status": "needsAction",
        }

        id_mapping = {}
        task = convert_task(gtask, "project1", id_mapping, {})

        self.assertIn("original_id_123", id_mapping)
        self.assertEqual(id_mapping["original_id_123"], task["id"])


class TestFullConversion(unittest.TestCase):
    """Test full conversion process."""

    def setUp(self):
        """Set up test data."""
        self.sample_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "My Tasks",
                    "updated": "2020-10-10T03:46:42.098751Z",
                    "items": [
                        {
                            "kind": "tasks#task",
                            "id": "task1",
                            "title": "Task One",
                            "status": "needsAction",
                            "updated": "2020-10-10T03:46:42.098751Z",
                        },
                        {
                            "kind": "tasks#task",
                            "id": "task2",
                            "title": "Task Two",
                            "status": "completed",
                            "completed": "2020-10-11T10:00:00Z",
                            "updated": "2020-10-10T03:46:42.098751Z",
                        },
                    ],
                },
            ],
        }

    def test_convert_sample_data(self):
        """Sample data should convert without errors."""
        result = convert_google_tasks_to_sp(self.sample_data)

        # Check CompleteBackup wrapper structure
        self.assertIn("data", result)
        self.assertIn("timestamp", result)
        self.assertIn("lastUpdate", result)
        self.assertIn("crossModelVersion", result)

        data = result["data"]
        self.assertIn("project", data)
        self.assertIn("task", data)
        self.assertEqual(len(data["project"]["ids"]), 1)
        self.assertEqual(len(data["task"]["ids"]), 2)

    def test_project_created(self):
        """Projects should be created from task lists."""
        result = convert_google_tasks_to_sp(self.sample_data)
        data = result["data"]

        project_id = data["project"]["ids"][0]
        project = data["project"]["entities"][project_id]

        self.assertEqual(project["title"], "My Tasks")
        self.assertIn("taskIds", project)
        self.assertIn("backlogTaskIds", project)

    def test_tasks_linked_to_project(self):
        """Tasks should be linked to their project."""
        result = convert_google_tasks_to_sp(self.sample_data)
        data = result["data"]

        project_id = data["project"]["ids"][0]

        for task_id in data["task"]["ids"]:
            task = data["task"]["entities"][task_id]
            self.assertEqual(task["projectId"], project_id)

    def test_empty_task_list(self):
        """Empty task lists should create empty projects."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "Empty List",
                    "updated": "2020-10-10T03:46:42.098751Z",
                    "items": [],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        self.assertEqual(len(data["project"]["ids"]), 1)
        self.assertEqual(len(data["task"]["ids"]), 0)

        project_id = data["project"]["ids"][0]
        project = data["project"]["entities"][project_id]
        self.assertEqual(project["taskIds"], [])

    def test_multiple_task_lists(self):
        """Multiple task lists should create multiple projects."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "List One",
                    "items": [{"id": "t1", "title": "Task 1", "status": "needsAction"}],
                },
                {
                    "kind": "tasks#tasks",
                    "id": "list2",
                    "title": "List Two",
                    "items": [{"id": "t2", "title": "Task 2", "status": "needsAction"}],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        self.assertEqual(len(data["project"]["ids"]), 2)
        self.assertEqual(len(data["task"]["ids"]), 2)


class TestSubtasks(unittest.TestCase):
    """Test subtask handling."""

    def test_subtask_relationships(self):
        """Subtasks should be properly linked to parents."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [
                        {
                            "id": "parent_task",
                            "title": "Parent Task",
                            "status": "needsAction",
                        },
                        {
                            "id": "child_task",
                            "title": "Child Task",
                            "parent": "parent_task",
                            "status": "needsAction",
                        },
                    ],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        # Find parent and child tasks
        parent_task = None
        child_task = None
        for task_id, task in data["task"]["entities"].items():
            if task["title"] == "Parent Task":
                parent_task = task
            elif task["title"] == "Child Task":
                child_task = task

        self.assertIsNotNone(parent_task)
        self.assertIsNotNone(child_task)

        # Child should reference parent
        self.assertEqual(child_task["parentId"], parent_task["id"])

        # Parent should list child in subTaskIds
        self.assertIn(child_task["id"], parent_task["subTaskIds"])

    def test_subtasks_not_in_project_taskids(self):
        """Subtasks should not appear in project.taskIds."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [
                        {
                            "id": "parent_task",
                            "title": "Parent Task",
                            "status": "needsAction",
                        },
                        {
                            "id": "child_task",
                            "title": "Child Task",
                            "parent": "parent_task",
                            "status": "needsAction",
                        },
                    ],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        project_id = data["project"]["ids"][0]
        project = data["project"]["entities"][project_id]

        # Only parent should be in project taskIds
        self.assertEqual(len(project["taskIds"]), 1)

        # Find child task ID
        child_task_id = None
        for task_id, task in data["task"]["entities"].items():
            if task["title"] == "Child Task":
                child_task_id = task_id

        self.assertNotIn(child_task_id, project["taskIds"])


class TestValidation(unittest.TestCase):
    """Test validation functions."""

    def test_valid_data_passes(self):
        """Valid data should pass validation."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "kind": "tasks#tasks",
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [
                        {"id": "task1", "title": "Task One", "status": "needsAction"},
                    ],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        errors = validate_sp_data(result)

        self.assertEqual(errors, [])

    def test_detect_invalid_project_reference(self):
        """Invalid project references should be detected."""
        backup = convert_google_tasks_to_sp({
            "kind": "tasks#taskLists",
            "items": [{"id": "list1", "title": "Test", "items": []}],
        })
        data = backup["data"]

        # Manually corrupt data
        data["task"]["ids"].append("bad_task")
        data["task"]["entities"]["bad_task"] = {
            "id": "bad_task",
            "title": "Bad Task",
            "projectId": "non_existent_project",
            "isDone": False,
            "subTaskIds": [],
        }

        errors = validate_sp_data(backup)
        self.assertTrue(any("non-existent project" in e for e in errors))

    def test_detect_circular_reference(self):
        """Circular parent references should be detected."""
        backup = convert_google_tasks_to_sp({
            "kind": "tasks#taskLists",
            "items": [{"id": "list1", "title": "Test", "items": []}],
        })
        data = backup["data"]

        # Create circular reference
        project_id = data["project"]["ids"][0]
        data["task"]["ids"] = ["task_a", "task_b"]
        data["task"]["entities"] = {
            "task_a": {
                "id": "task_a",
                "title": "Task A",
                "projectId": project_id,
                "parentId": "task_b",
                "isDone": False,
                "subTaskIds": [],
            },
            "task_b": {
                "id": "task_b",
                "title": "Task B",
                "projectId": project_id,
                "parentId": "task_a",
                "isDone": False,
                "subTaskIds": [],
            },
        }

        errors = validate_sp_data(backup)
        self.assertTrue(any("Circular" in e for e in errors))


class TestUnicode(unittest.TestCase):
    """Test Unicode handling."""

    def test_unicode_titles(self):
        """Unicode titles should be preserved."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "id": "list1",
                    "title": "日本語タスク",
                    "items": [
                        {"id": "t1", "title": "任務一 🎯", "status": "needsAction"},
                        {"id": "t2", "title": "Tâche française", "status": "needsAction"},
                    ],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        project_id = data["project"]["ids"][0]
        project = data["project"]["entities"][project_id]
        self.assertEqual(project["title"], "日本語タスク")

        titles = [t["title"] for t in data["task"]["entities"].values()]
        self.assertIn("任務一 🎯", titles)
        self.assertIn("Tâche française", titles)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_input(self):
        """Empty items array should work."""
        input_data = {"kind": "tasks#taskLists", "items": []}
        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        self.assertEqual(len(data["project"]["ids"]), 0)
        self.assertEqual(len(data["task"]["ids"]), 0)

    def test_missing_task_title(self):
        """Missing task title should become 'Untitled Task'."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [{"id": "t1", "title": "", "status": "needsAction"}],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        task = list(data["task"]["entities"].values())[0]
        self.assertEqual(task["title"], "Untitled Task")

    def test_task_without_id(self):
        """Tasks without IDs should still get UUIDs."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [{"title": "No ID Task", "status": "needsAction"}],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        self.assertEqual(len(data["task"]["ids"]), 1)
        task = list(data["task"]["entities"].values())[0]
        self.assertTrue(len(task["id"]) > 0)

    def test_duplicate_task_ids(self):
        """Tasks with duplicate IDs should each get unique UUIDs."""
        input_data = {
            "kind": "tasks#taskLists",
            "items": [
                {
                    "id": "list1",
                    "title": "My Tasks",
                    "items": [
                        {"id": "SAME_ID", "title": "Task One", "status": "needsAction"},
                        {"id": "SAME_ID", "title": "Task Two", "status": "needsAction"},
                    ],
                },
                {
                    "id": "list2",
                    "title": "Second List",
                    "items": [
                        {"id": "SAME_ID", "title": "Task Three", "status": "needsAction"},
                        {"id": "SAME_ID", "title": "Task Four", "status": "needsAction"},
                    ],
                },
            ],
        }

        result = convert_google_tasks_to_sp(input_data)
        data = result["data"]

        # Should have 4 unique tasks despite duplicate original IDs
        self.assertEqual(len(data["task"]["ids"]), 4)
        self.assertEqual(len(data["task"]["entities"]), 4)

        # All task IDs should be unique
        task_ids = data["task"]["ids"]
        self.assertEqual(len(task_ids), len(set(task_ids)))

        # All titles should be present
        titles = [t["title"] for t in data["task"]["entities"].values()]
        self.assertIn("Task One", titles)
        self.assertIn("Task Two", titles)
        self.assertIn("Task Three", titles)
        self.assertIn("Task Four", titles)

        # Validation should pass
        errors = validate_sp_data(result)
        self.assertEqual(errors, [])


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()
