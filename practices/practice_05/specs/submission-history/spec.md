# Spec Delta

## Purpose

Enables authenticated users to retrieve, inspect, and restore their historical code submissions for algorithmic practice problems.

## ADDED Requirements

### Requirement: Authenticated Submission History Retrieval
The system SHALL provide an authenticated API endpoint `GET /api/problems/{id}/submissions` that returns a list of previous submissions for the specified problem, scoped strictly to the authenticated user and ordered newest first (up to a limit of 20 entries).

#### Scenario: Authenticated user retrieves submission history
- **WHEN** an authenticated user issues a GET request to `/api/problems/{id}/submissions` for a problem they have submitted solutions to
- **THEN** the system returns HTTP 200 with an array of submission records containing `id`, `problem_id`, `language`, `code`, `status`, `runtime_ms`, `memory_mb`, `passed_tests`, `total_tests`, and `created_at` ordered by `created_at` descending

#### Scenario: Authenticated user with no submissions
- **WHEN** an authenticated user issues a GET request to `/api/problems/{id}/submissions` for a problem with no prior submissions
- **THEN** the system returns HTTP 200 with an empty JSON array `[]`

#### Scenario: Unauthenticated request rejected
- **WHEN** an unauthenticated request is sent to `GET /api/problems/{id}/submissions`
- **THEN** the system returns HTTP 401 Unauthorized

### Requirement: Problem Workspace Submissions Tab Visibility
The system SHALL present a "Submissions" tab in the left panel of the problem workspace alongside "Description" if and only if the current user is authenticated.

#### Scenario: Authenticated user views problem workspace
- **WHEN** an authenticated user navigates to the problem workspace
- **THEN** the left panel displays both the "Description" tab and the "Submissions" tab

#### Scenario: Guest user views problem workspace
- **WHEN** an unauthenticated visitor navigates to the problem workspace
- **THEN** the left panel displays only the "Description" tab, and the "Submissions" tab is omitted

### Requirement: Past Submission Inspection and Code Restoration
The system SHALL permit users to inspect a past submission's code and execution details in a read-only modal viewer, and allow restoring that code into the active Monaco editor.

#### Scenario: User opens submission details modal
- **WHEN** a user clicks on a submission item in the Submissions tab
- **THEN** a read-only modal opens showing the submission verdict status, execution runtime, memory usage, passed test counts, submission timestamp, and the submitted source code

#### Scenario: User restores submission code to editor
- **WHEN** a user clicks the "Restore to editor" action in the submission details modal
- **THEN** the submission modal closes and the active editor's contents and selected language are updated to match the restored submission
