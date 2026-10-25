# Tasks

## 1. Backend Data Model & Repository

- [x] 1.1 Add `SubmissionRecord` struct in `backend/internal/models/problem.go` with JSON annotations and verify with `go test -v ./internal/models/...`
- [x] 1.2 Add `GetSubmissions(userID int64, problemID string, limit int) ([]models.SubmissionRecord, error)` to repository interface and PostgreSQL implementation in `backend/internal/repository/postgres.go`, update mocks in `backend/internal/handlers/api_test.go`, and verify with `go test -v ./internal/repository/...`

## 2. Backend Handler & Route

- [x] 2.1 Implement `GetProblemSubmissions` handler in `backend/internal/handlers/api.go` extracting authenticated user ID and problem ID with a limit of 20
- [x] 2.2 Add unit test cases in `backend/internal/handlers/api_test.go` covering authenticated retrieval, unauthenticated 401 response, and empty results, and verify with `go test -v ./internal/handlers/...`

## 3. Frontend API Client & Types

- [x] 3.1 Define `Submission` interface in `frontend/src/types/problem.ts` and add `getSubmissions(problemId: string)` to `frontend/src/services/api.ts`
- [x] 3.2 Add unit tests in `frontend/src/services/api.test.ts` verifying API request and auth header handling, and verify with `npm test -- run frontend/src/services/api.test.ts`

## 4. Problem Workspace UI Integration

- [x] 4.1 Update `frontend/src/components/ProblemWorkspace.tsx` to conditionally display the "Submissions" tab for authenticated users and fetch historical records on tab activation
- [x] 4.2 Implement submission list rendering and a read-only code inspection modal with a "Restore to editor" action in `frontend/src/components/ProblemWorkspace.tsx`
- [x] 4.3 Update `frontend/src/components/ProblemWorkspace.test.tsx` with tests for tab conditional visibility, submission list display, and code restoration, verifying with `npm test -- run frontend/src/components/ProblemWorkspace.test.tsx`

## 5. Integration Verification

- [x] 5.1 Run the project verification suite `./scripts/verify-tests.sh` and verify all Go tests, TypeScript compilation, and Vite builds succeed
