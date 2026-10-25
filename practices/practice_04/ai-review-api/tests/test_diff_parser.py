"""Тесты разбора diff для MCP diff-inspector (чистый Python, без mcp)."""

import pytest

from mcp_server.diff_parser import DiffInspectError, inspect_diff

MODIFIED = """\
diff --git a/app/main.py b/app/main.py
index 111..222 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,4 +1,5 @@
 import os
-old = 1
-old2 = 2
+new = 1
+new2 = 2
+new3 = 3
 print(old)
@@ -10,2 +11,2 @@ def f():
 x = 1
-y = 2
+y = 3
"""

NEW_FILE = """\
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+hello
+world
"""

DELETED = """\
diff --git a/old.txt b/old.txt
deleted file mode 100644
index abc..0000000
--- a/old.txt
+++ /dev/null
@@ -1,3 +0,0 @@
-a
-b
-c
"""

RENAMED = """\
diff --git a/src/a.py b/src/b.py
similarity index 90%
rename from src/a.py
rename to src/b.py
index 111..222 100644
--- a/src/a.py
+++ b/src/b.py
@@ -1 +1 @@
-print(1)
+print(2)
"""

RENAMED_PURE = """\
diff --git a/a.txt b/c.txt
similarity index 100%
rename from a.txt
rename to c.txt
"""

BINARY = """\
diff --git a/img/logo.png b/img/logo.png
new file mode 100644
index 0000000..abc
Binary files /dev/null and b/img/logo.png differ
"""


def test_modified_file_counts():
    r = inspect_diff(MODIFIED)
    assert r["total_files"] == 1
    f = r["files"][0]
    assert f["path"] == "app/main.py"
    assert f["status"] == "modified"
    assert (f["added"], f["removed"]) == (4, 3)
    assert (r["total_added"], r["total_removed"]) == (4, 3)
    assert r["too_large"] is False
    assert r["would_be_accepted"] is True


def test_size_is_utf8_bytes():
    diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+привет\n"
    r = inspect_diff(diff)
    assert r["size_bytes"] == len(diff.encode("utf-8"))
    assert r["size_bytes"] > len(diff)  # кириллица: байт больше, чем символов


def test_new_file():
    f = inspect_diff(NEW_FILE)["files"][0]
    assert f["path"] == "docs/new.md"
    assert f["status"] == "added"
    assert (f["added"], f["removed"]) == (2, 0)


def test_deleted_file():
    f = inspect_diff(DELETED)["files"][0]
    assert f["path"] == "old.txt"
    assert f["status"] == "deleted"
    assert (f["added"], f["removed"]) == (0, 3)


def test_rename_with_changes():
    f = inspect_diff(RENAMED)["files"][0]
    assert f["status"] == "renamed"
    assert f["old_path"] == "src/a.py"
    assert f["path"] == "src/b.py"
    assert (f["added"], f["removed"]) == (1, 1)


def test_pure_rename_without_hunks():
    r = inspect_diff(RENAMED_PURE)
    f = r["files"][0]
    assert (f["old_path"], f["path"], f["status"]) == ("a.txt", "c.txt", "renamed")
    assert (f["added"], f["removed"]) == (0, 0)
    assert r["would_be_accepted"] is True


def test_binary_file():
    f = inspect_diff(BINARY)["files"][0]
    assert f["binary"] is True
    assert f["status"] == "added"
    assert f["path"] == "img/logo.png"
    assert (f["added"], f["removed"]) == (0, 0)


def test_multiple_files_totals():
    r = inspect_diff(MODIFIED + NEW_FILE + DELETED + BINARY)
    assert [f["path"] for f in r["files"]] == ["app/main.py", "docs/new.md", "old.txt", "img/logo.png"]
    assert r["total_files"] == 4
    assert r["total_added"] == 4 + 2
    assert r["total_removed"] == 3 + 3


def test_content_lines_that_look_like_headers_are_counted_as_content():
    # внутри ханка строки "--- x" и "+++ y" это удаление/добавление, а не заголовки файла
    diff = (
        "diff --git a/n.md b/n.md\n--- a/n.md\n+++ b/n.md\n"
        "@@ -1,2 +1,2 @@\n"
        "--- removed line starting with dashes\n"
        "+++ added line starting with pluses\n"
    )
    r = inspect_diff(diff)
    assert r["total_files"] == 1
    assert (r["total_added"], r["total_removed"]) == (1, 1)


def test_no_newline_marker_not_counted():
    diff = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n\\ No newline at end of file\n"
    r = inspect_diff(diff)
    assert (r["total_added"], r["total_removed"]) == (1, 1)


def test_crlf_diff():
    r = inspect_diff(MODIFIED.replace("\n", "\r\n"))
    assert r["files"][0]["path"] == "app/main.py"
    assert (r["total_added"], r["total_removed"]) == (4, 3)


def test_plain_unified_diff_without_git_header():
    diff = "--- a/one.txt\t2020-01-01\n+++ b/one.txt\t2020-01-02\n@@ -1 +1 @@\n-a\n+b\n--- a/two.txt\n+++ b/two.txt\n@@ -1 +1,2 @@\n a\n+c\n"
    r = inspect_diff(diff)
    assert [f["path"] for f in r["files"]] == ["one.txt", "two.txt"]
    assert (r["total_added"], r["total_removed"]) == (2, 1)


def test_path_with_spaces():
    diff = "diff --git a/my dir/a b.txt b/my dir/a b.txt\n--- a/my dir/a b.txt\n+++ b/my dir/a b.txt\n@@ -1 +1 @@\n-a\n+b\n"
    assert inspect_diff(diff)["files"][0]["path"] == "my dir/a b.txt"


def test_blank_context_line_inside_hunk():
    # редакторы иногда обрезают пробел у пустой контекстной строки
    diff = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1,3 +1,3 @@\n a\n\n-b\n+c\n"
    r = inspect_diff(diff)
    assert (r["total_added"], r["total_removed"]) == (1, 1)


# граница размера

def test_size_exactly_at_limit_is_accepted():
    size = len(NEW_FILE.encode("utf-8"))
    r = inspect_diff(NEW_FILE, max_bytes=size)
    assert r["too_large"] is False
    assert r["would_be_accepted"] is True


def test_size_one_byte_over_limit_is_too_large():
    size = len(NEW_FILE.encode("utf-8"))
    r = inspect_diff(NEW_FILE, max_bytes=size - 1)
    assert r["too_large"] is True
    assert r["would_be_accepted"] is False
    assert r["total_files"] == 1  # разбор все равно сделан


def test_default_limit_is_100000():
    r = inspect_diff(NEW_FILE)
    assert r["max_bytes"] == 100000
    big = "diff --git a/b b/b\n--- a/b\n+++ b/b\n@@ -0,0 +1 @@\n+" + "x" * 100000 + "\n"
    assert inspect_diff(big)["too_large"] is True


# ошибки

@pytest.mark.parametrize("bad", ["", " ", "   \n\t\n"])
def test_empty_or_whitespace_is_error(bad):
    with pytest.raises(DiffInspectError, match="пуст|пробел"):
        inspect_diff(bad)


def test_empty_and_whitespace_messages_differ():
    with pytest.raises(DiffInspectError) as e1:
        inspect_diff("")
    with pytest.raises(DiffInspectError) as e2:
        inspect_diff("   ")
    assert "пустой" in str(e1.value)
    assert "пробел" in str(e2.value)


@pytest.mark.parametrize("junk", ["hello world", "just some text\nwith lines", "{\"json\": true}", "+added\n-removed"])
def test_text_without_diff_markers_is_error(junk):
    with pytest.raises(DiffInspectError, match="признак"):
        inspect_diff(junk)


def test_hunk_without_file_header_is_error():
    with pytest.raises(DiffInspectError):
        inspect_diff("@@ -1 +1 @@\n-a\n+b\n")


@pytest.mark.parametrize("bad", [0, -1, -100000])
def test_non_positive_max_bytes_is_error(bad):
    with pytest.raises(DiffInspectError, match="max_bytes"):
        inspect_diff(NEW_FILE, max_bytes=bad)


@pytest.mark.parametrize("bad", ["100", 1.5, None, True])
def test_non_int_max_bytes_is_error(bad):
    with pytest.raises(DiffInspectError, match="max_bytes"):
        inspect_diff(NEW_FILE, max_bytes=bad)


@pytest.mark.parametrize("bad", [None, 123, b"diff --git a/x b/x", ["diff"]])
def test_non_string_diff_is_error(bad):
    with pytest.raises(DiffInspectError, match="строкой"):
        inspect_diff(bad)


def test_error_is_value_error():
    assert issubclass(DiffInspectError, ValueError)
