"""
Unit tests for markdown parsing with XML tag support.

Tests parse_task_section(), generate_markdown_task(), and round-trip preservation
with focus on XML-wrapped descriptions and session logs.
"""

import unittest
import os
import sys
import json
from tests.test_helpers import TempReadyQTest
import readyq


class TestXMLTagParsing(TempReadyQTest):
    """Test XML tag parsing in descriptions and session logs."""

    def test_parse_description_with_xml_tags(self):
        """Test parsing description wrapped in <description> tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "This is a **bold** description"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "This is a **bold** description")

    def test_parse_session_log_with_xml_tags(self):
        """Test parsing session logs wrapped in <log> tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "First log entry"}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "First log entry")

    def test_parse_multiline_description_with_xml_tags(self):
        """Test parsing multiline description with XML tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "Line 1\nLine 2\nLine 3"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "Line 1\nLine 2\nLine 3")

    def test_parse_multiline_session_log_with_xml_tags(self):
        """Test parsing multiline session log with XML tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "Log line 1\nLog line 2\nLog line 3"}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "Log line 1\nLog line 2\nLog line 3")


class TestMarkdownHeadersInDescriptions(TempReadyQTest):
    """Test descriptions containing markdown headers."""

    def test_description_with_h2_header(self):
        """Test description with ## header."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "## This is a header\nSome content below"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "## This is a header\nSome content below")

    def test_description_with_h3_header(self):
        """Test description with ### header."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "### Subsection\nContent here"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "### Subsection\nContent here")

    def test_description_with_multiple_headers(self):
        """Test description with multiple headers."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "## Section 1\nContent 1\n\n### Subsection\nContent 2\n\n## Section 2\nContent 3"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "## Section 1\nContent 1\n\n### Subsection\nContent 2\n\n## Section 2\nContent 3")

    def test_session_log_with_headers(self):
        """Test session log containing headers."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "## Work Done\nImplemented feature\n\n### Testing\nRan tests"}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "## Work Done\nImplemented feature\n\n### Testing\nRan tests")


class TestHorizontalRulesInContent(TempReadyQTest):
    """Test content containing horizontal rules (---)."""

    def test_description_with_horizontal_rule(self):
        """Test description containing --- horizontal rule."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "Section 1\n\n---\n\nSection 2"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "Section 1\n\n---\n\nSection 2")

    def test_description_with_multiple_horizontal_rules(self):
        """Test description with multiple --- rules."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "Part 1\n---\nPart 2\n---\nPart 3"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "Part 1\n---\nPart 2\n---\nPart 3")

    def test_session_log_with_horizontal_rule(self):
        """Test session log containing --- horizontal rule."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "Before\n---\nAfter"}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "Before\n---\nAfter")


class TestXMLLikeContentInDescriptions(TempReadyQTest):
    """Test content that looks like XML tags."""

    def test_description_with_html_tags(self):
        """Test description containing HTML/XML tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "Use <div> and <span> tags in HTML"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "Use <div> and <span> tags in HTML")

    def test_description_with_xml_entities(self):
        """Test description with XML entities like &amp;."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "Use &amp; for ampersands and &lt; for less-than"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "Use &amp; for ampersands and &lt; for less-than")

    def test_description_with_angle_brackets(self):
        """Test description with angle brackets < >."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "if x < 5 and y > 10"

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "if x < 5 and y > 10")

    def test_session_log_with_code_snippets(self):
        """Test session log containing code with <> characters."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "Fixed: vector<int> should be vector<string>"}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "Fixed: vector<int> should be vector<string>")


class TestEmptyContent(TempReadyQTest):
    """Test empty descriptions and session logs with XML tags."""

    def test_empty_description_with_xml_tags(self):
        """Test task with empty description in XML tags."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = ""

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].get('description', ''), "")

    def test_whitespace_only_description(self):
        """Test description with only whitespace."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['description'] = "   \n   \n   "

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        # Should be stripped to empty or minimal whitespace
        self.assertIn(tasks[0].get('description', '').strip(), ['', '   \n   \n   '])

    def test_empty_session_log(self):
        """Test session log with empty content."""
        task_dict = self.create_task_dict("Test Task")
        task_dict['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": ""}
        ]

        markdown = readyq.generate_markdown_task(task_dict)
        self.save_markdown_task(markdown)

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(tasks[0]['sessions']), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "")


class TestMalformedXMLTags(TempReadyQTest):
    """Test handling of malformed XML tags."""

    def test_unclosed_description_tag(self):
        """Test parsing with unclosed <description> tag."""
        # Manually create markdown with unclosed tag
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'w') as f:
            f.write("# Task: Test Task\n\n")
            f.write("**ID**: abc123\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("<description>\n")
            f.write("Missing closing tag\n")
            # No </description> tag

        # Should fallback to legacy parser or handle gracefully
        tasks = readyq.md_load_tasks()
        # May or may not parse - test that it doesn't crash
        self.assertIsInstance(tasks, list)

    def test_mismatched_xml_tags(self):
        """Test parsing with mismatched tags."""
        # Manually create markdown with mismatched tags
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'w') as f:
            f.write("# Task: Test Task\n\n")
            f.write("**ID**: abc123\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("<description>\n")
            f.write("Content here\n")
            f.write("</log>\n")  # Wrong closing tag

        # Should handle gracefully
        tasks = readyq.md_load_tasks()
        self.assertIsInstance(tasks, list)


class TestTaskSeparatorRegex(TempReadyQTest):
    """Test task separator regex with --- in various positions."""

    def test_task_separator_on_own_line(self):
        """Test proper task separator: newline-dash-newline."""
        task1 = self.create_task_dict("Task 1")
        task2 = self.create_task_dict("Task 2")

        readyq.md_save_tasks([task1, task2])

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Task 1")
        self.assertEqual(tasks[1]['title'], "Task 2")

    def test_horizontal_rule_in_description_not_separator(self):
        """Test that --- inside description doesn't split tasks."""
        task1 = self.create_task_dict("Task 1")
        task1['description'] = "Before\n---\nAfter"
        task2 = self.create_task_dict("Task 2")

        readyq.md_save_tasks([task1, task2])

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['description'], "Before\n---\nAfter")

    def test_inline_dashes_not_separator(self):
        """Test that inline --- (not on own line) doesn't split tasks."""
        task1 = self.create_task_dict("Task 1")
        task1['description'] = "Text with --- dashes in middle"
        task2 = self.create_task_dict("Task 2")

        readyq.md_save_tasks([task1, task2])

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['description'], "Text with --- dashes in middle")


class TestBackwardCompatibility(TempReadyQTest):
    """Test backward compatibility with legacy format (no XML tags)."""

    def test_load_legacy_description_format(self):
        """Test loading description without <description> tags."""
        # Manually create markdown in legacy format
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'w') as f:
            f.write("# Task: Legacy Task\n\n")
            f.write("**ID**: abc123\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("This is a legacy description without XML tags.\n")

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], "This is a legacy description without XML tags.")

    def test_load_legacy_session_log_format(self):
        """Test loading session log without <log> tags."""
        # Manually create markdown with legacy session log format
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'w') as f:
            f.write("# Task: Legacy Task\n\n")
            f.write("**ID**: abc123\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("Description here\n")
            f.write("\n## Session Logs\n\n")
            f.write("### 2025-11-26T10:00:00+00:00\n")
            f.write("Legacy log entry without XML tags\n")

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(tasks[0].get('sessions', [])), 1)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "Legacy log entry without XML tags")

    def test_load_mixed_legacy_and_xml_formats(self):
        """Test loading file with mix of legacy and XML formats."""
        # Create file with two tasks: one legacy, one XML
        md_path = self.db_path.replace('.jsonl', '.md')
        with open(md_path, 'w') as f:
            # Legacy task
            f.write("# Task: Legacy Task\n\n")
            f.write("**ID**: abc123\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("Legacy description\n")

            f.write("\n---\n\n")

            # XML task
            f.write("# Task: XML Task\n\n")
            f.write("**ID**: def456\n")
            f.write("**Created**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Updated**: 2025-11-26T10:00:00+00:00\n")
            f.write("**Blocks**: \n")
            f.write("**Blocked By**: \n")
            f.write("\n## Status\n\n")
            f.write("- [x] Open\n")
            f.write("- [ ] In Progress\n")
            f.write("- [ ] Blocked\n")
            f.write("- [ ] Done\n")
            f.write("\n## Description\n\n")
            f.write("<description>\n")
            f.write("XML description\n")
            f.write("</description>\n")

        tasks = readyq.md_load_tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['title'], "Legacy Task")
        self.assertEqual(tasks[0]['description'], "Legacy description")
        self.assertEqual(tasks[1]['title'], "XML Task")
        self.assertEqual(tasks[1]['description'], "XML description")


class TestRoundTripPreservation(TempReadyQTest):
    """Test that content is preserved through save → load cycles."""

    def test_round_trip_simple_description(self):
        """Test round-trip with simple description."""
        original = self.create_task_dict("Test Task")
        original['description'] = "Simple description"

        # Save
        readyq.md_save_tasks([original])

        # Load
        tasks = readyq.md_load_tasks()

        # Verify
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], original['description'])

    def test_round_trip_complex_markdown(self):
        """Test round-trip with complex markdown in description."""
        original = self.create_task_dict("Test Task")
        original['description'] = "## Header\n\n**Bold** and *italic*\n\n- List item 1\n- List item 2\n\n```python\ncode block\n```"

        readyq.md_save_tasks([original])
        tasks = readyq.md_load_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], original['description'])

    def test_round_trip_with_headers_and_horizontal_rules(self):
        """Test round-trip with headers and horizontal rules."""
        original = self.create_task_dict("Test Task")
        original['description'] = "## Section 1\nContent\n---\n## Section 2\nMore content"

        readyq.md_save_tasks([original])
        tasks = readyq.md_load_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], original['description'])

    def test_round_trip_multiple_session_logs(self):
        """Test round-trip with multiple session logs."""
        original = self.create_task_dict("Test Task")
        original['sessions'] = [
            {"timestamp": "2025-11-26T10:00:00+00:00", "log": "First log\n## Work done\nStuff"},
            {"timestamp": "2025-11-26T11:00:00+00:00", "log": "Second log\n---\nSeparated content"},
            {"timestamp": "2025-11-26T12:00:00+00:00", "log": "Third log"}
        ]

        readyq.md_save_tasks([original])
        tasks = readyq.md_load_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(tasks[0]['sessions']), 3)
        self.assertEqual(tasks[0]['sessions'][0]['log'], "First log\n## Work done\nStuff")
        self.assertEqual(tasks[0]['sessions'][1]['log'], "Second log\n---\nSeparated content")
        self.assertEqual(tasks[0]['sessions'][2]['log'], "Third log")

    def test_round_trip_special_characters(self):
        """Test round-trip with special characters."""
        original = self.create_task_dict("Test Task")
        original['description'] = "Special chars: <>&\"'\n&amp; &lt; &gt;"

        readyq.md_save_tasks([original])
        tasks = readyq.md_load_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], original['description'])


if __name__ == '__main__':
    unittest.main()
