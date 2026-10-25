# Proposal

## Why

Users can submit code solutions on AlgoPlace, and submissions are stored in the PostgreSQL database, but there is currently no way for users to view their past attempts. Users need to review their previous submissions, inspect historical solutions (both accepted and failed), and reload past code into the editor without losing context.

## What Changes

- Add backend API endpoint `GET /api/problems/{id}/submissions` returning historical submissions for the authenticated user and problem.
- Add repository method `GetSubmissions(userID int64, problemID string, limit int)` querying the existing `submissions` table sorted by creation date descending.
- Extend frontend `apiService` and TypeScript models with submission history support.
- In `ProblemWorkspace`, add a `Submissions` tab to the left panel (alongside `Description`), visible exclusively to authenticated users.
- Provide a read-only modal/inspection view for past submissions showing code, verdict status, runtime, memory, and passed test metrics, with a "Restore to editor" button.

## Capabilities

### New Capabilities
- `submission-history`: Querying and viewing past problem submissions and submitted code for authenticated users.

### Modified Capabilities
*(None)*

## Impact

- **Backend**:
  - `backend/internal/models/problem.go`: Add `Submission` response model.
  - `backend/internal/repository/postgres.go` & `interfaces.go`: Implement `GetSubmissions`.
  - `backend/internal/handlers/api.go`: Add route handler for `GET /api/problems/{id}/submissions`.
- **Frontend**:
  - `frontend/src/types/problem.ts`: Add `Submission` interface.
  - `frontend/src/services/api.ts`: Add `getSubmissions(problemId)`.
  - `frontend/src/components/ProblemWorkspace.tsx`: Render Submissions tab and inspection modal.
- **Database**:
  - Uses existing PostgreSQL `submissions` table without schema changes.
