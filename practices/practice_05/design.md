# Design

## Context

AlgoPlace already stores problem submissions in a PostgreSQL `submissions` table via `SaveSubmission` during `POST /api/submissions/submit`. However, there is no read path exposed via HTTP or UI.
User authentication is managed via JWT tokens parsed into request contexts using `auth.GetUserFromContext(r.Context())`.
On the frontend, `ProblemWorkspace.tsx` manages problem viewing, code editing, and execution, with an `activeTab` state on the left pane currently showing only the problem description.

See `proposal.md` for feature motivation and `specs/submission-history/spec.md` for behavior requirements.

## Goals / Non-Goals

**Goals:**
- Provide a dedicated, authenticated endpoint to fetch the user's historical submissions for a specific problem.
- Display a clean submission history list on the left pane of `ProblemWorkspace`.
- Provide a read-only modal to inspect past submission metadata and source code.
- Allow restoring past submission code into the active editor safely.

**Non-Goals:**
- Global multi-problem submission log in the user profile (can be added in future iterations).
- Public submission visibility or cross-user leaderboard.
- Code diff tool between different submissions.
- Re-judging past submissions against new test cases.

## Decisions

### 1. API Route: `GET /api/problems/{id}/submissions`
- **Choice**: Nest the submissions endpoint under the problem resource path (`/api/problems/{id}/submissions`).
- **Rationale**: Keeps problem-scoped querying consistent with `GET /api/problems/{slug}`. Scoped to the authenticated user from JWT claims.
- **Alternative considered**: Top-level `GET /api/submissions?problemId={id}`. Rejected to avoid ambiguity about global vs scoped access in the initial MVP.

### 2. Reuse Existing PostgreSQL Schema
- **Choice**: Query the existing `submissions` table directly:
  ```sql
  SELECT id, problem_id, language, code, status, runtime_ms, memory_mb, passed_tests, total_tests, created_at
  FROM submissions
  WHERE user_id = $1 AND problem_id = $2
  ORDER BY created_at DESC
  LIMIT $3
  ```
- **Rationale**: The schema already records `language`, `code`, `status`, `runtime_ms`, `memory_mb`, `passed_tests`, `total_tests`, and `created_at`. No database migrations are necessary. A default limit of 20 avoids excessive payload size.

### 3. Frontend UI Placement in ProblemWorkspace
- **Choice**: Add a `Submissions` tab on the left pane of `ProblemWorkspace` alongside `Description`, visible only when `isLoggedIn` is true.
- **Rationale**: Follows standard online judge UX (e.g. LeetCode), keeping problem notes and history within immediate reach without cluttering the bottom test console.
- **Alternative considered**: Bottom console tab next to "Testcase" and "Result". Rejected because the console is focused on transient runs/tests, whereas submissions are permanent problem history.

### 4. Read-Only Modal for Code Inspection & Restoration
- **Choice**: Clicking a submission row opens a modal dialog displaying verdict metrics, timestamp, and the submitted source code with syntax highlighting / read-only Monaco view, featuring a "Restore to editor" button.
- **Rationale**: Prevents accidental overwriting of the user's current working code in Monaco Editor while browsing history. Restoring updates both the code state and the selected language dropdown.

## Risks / Trade-offs

- **[Risk: Accidental overwrite of active editor code on restore]**
  - *Mitigation*: Inspection is read-only by default in a separate modal; restoring requires an explicit user click on "Restore to editor".
- **[Risk: Multiple simultaneous network requests on tab switches]**
  - *Mitigation*: Fetch submissions when switching to the `Submissions` tab and re-fetch automatically after a successful submission evaluation in `handleSubmit`.
