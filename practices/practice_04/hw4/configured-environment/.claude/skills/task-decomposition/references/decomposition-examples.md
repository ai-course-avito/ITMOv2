# Decomposition Examples

Complete worked examples showing how to decompose features into atomic implementation tasks for Python (FastAPI) + React/TypeScript projects.

---

## Example 1: Add User Authentication (8 Tasks)

**Objective:** Add JWT-based authentication with login, registration, and protected routes.

### Task 1: Add User model and migration
- **Files:** `backend/models/user.py`, `backend/migrations/versions/xxxx_add_user.py`
- **Preconditions:** None
- **Steps:**
  1. Create `User` SQLAlchemy model with fields: id, email, hashed_password, is_active, created_at
  2. Add unique index on email
  3. Generate Alembic migration with `alembic revision --autogenerate -m "add_user_table"`
  4. Run migration with `alembic upgrade head`
- **Done when:** `alembic current` shows latest revision AND `SELECT * FROM users` returns empty table
- **Complexity:** small

### Task 2: Create auth schemas
- **Files:** `backend/schemas/auth.py`
- **Preconditions:** None (parallel with Task 1)
- **Steps:**
  1. Create Pydantic v2 schemas: `UserCreate(email, password)`, `UserResponse(id, email, is_active, created_at)`, `TokenResponse(access_token, token_type)`
  2. Add email validation with `EmailStr`
  3. Add password length validation (min 8 chars)
- **Done when:** `python -c "from backend.schemas.auth import UserCreate, UserResponse, TokenResponse"` succeeds
- **Complexity:** trivial

### Task 3: Create auth service
- **Files:** `backend/services/auth_service.py`, `backend/core/security.py`
- **Preconditions:** Task 1, Task 2
- **Steps:**
  1. Create `security.py` with password hashing (bcrypt) and JWT token creation/verification
  2. Create `AuthService` class with methods: `register_user()`, `authenticate_user()`, `get_current_user()`
  3. Use async SQLAlchemy session for database operations
- **Done when:** `pytest tests/unit/test_auth_service.py -x` passes
- **Complexity:** medium

### Task 4: Create auth routes
- **Files:** `backend/routes/auth.py`, `backend/routes/__init__.py`
- **Preconditions:** Task 3
- **Steps:**
  1. Create `POST /auth/register` endpoint using `UserCreate` schema
  2. Create `POST /auth/login` endpoint returning `TokenResponse`
  3. Create `GET /auth/me` endpoint with JWT dependency returning `UserResponse`
  4. Register router in `__init__.py`
- **Done when:** `pytest tests/integration/test_auth_routes.py -x` passes
- **Complexity:** medium

### Task 5: Create auth dependency
- **Files:** `backend/dependencies/auth.py`
- **Preconditions:** Task 3
- **Steps:**
  1. Create `get_current_user` FastAPI dependency that extracts and validates JWT from Authorization header
  2. Create `require_active_user` dependency that checks `is_active` flag
- **Done when:** `pytest tests/unit/test_auth_dependency.py -x` passes
- **Complexity:** small

### Task 6: Create frontend auth hooks and context
- **Files:** `frontend/src/hooks/useAuth.ts`, `frontend/src/contexts/AuthContext.tsx`
- **Preconditions:** Task 4
- **Steps:**
  1. Create `AuthContext` with user state, login, logout, register functions
  2. Create `useAuth()` hook wrapping the context
  3. Store JWT in localStorage with automatic header injection via axios/fetch interceptor
  4. Add token expiration handling
- **Done when:** `npm test -- --grep "useAuth"` passes
- **Complexity:** medium

### Task 7: Create login and register pages
- **Files:** `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/RegisterPage.tsx`
- **Preconditions:** Task 6
- **Steps:**
  1. Create `LoginPage` with email/password form, validation, error display
  2. Create `RegisterPage` with email/password/confirm form, validation, error display
  3. Add routes in router configuration
  4. Add navigation between login and register
- **Done when:** `npm test -- --grep "LoginPage|RegisterPage"` passes
- **Complexity:** medium

### Task 8: Add protected route wrapper
- **Files:** `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/App.tsx`
- **Preconditions:** Task 6, Task 7
- **Steps:**
  1. Create `ProtectedRoute` component that redirects to `/login` if not authenticated
  2. Wrap protected page routes in `App.tsx`
  3. Add loading state while checking authentication
- **Done when:** `npm test -- --grep "ProtectedRoute"` passes AND manual verification: unauthenticated access to protected route redirects to login
- **Complexity:** small

**Dependency Graph:**
```
Task 1 (model) ──→ Task 3 (service) ──→ Task 4 (routes) ──→ Task 6 (hooks)
                         ↓                                       ↓
Task 2 (schemas) ───────┘                                  Task 7 (pages)
                                                                ↓
                   Task 5 (dependency) ──────────────→ Task 8 (protected route)
```

---

## Example 2: Add Full-Text Search (6 Tasks)

**Objective:** Add full-text search to an existing articles/posts resource using PostgreSQL tsvector.

### Task 1: Add search vector column and index
- **Files:** `backend/models/article.py`, `backend/migrations/versions/xxxx_add_search_vector.py`
- **Preconditions:** None
- **Steps:**
  1. Add `search_vector` column of type `TSVectorType` to Article model
  2. Create GIN index on `search_vector`
  3. Add trigger to auto-update search_vector on INSERT/UPDATE from title + body
  4. Generate and run Alembic migration
  5. Backfill existing articles with search vectors
- **Done when:** `alembic current` shows latest AND `SELECT count(*) FROM articles WHERE search_vector IS NOT NULL` matches total article count
- **Complexity:** medium

### Task 2: Create search repository method
- **Files:** `backend/repositories/article_repo.py`
- **Preconditions:** Task 1
- **Steps:**
  1. Add `search(query: str, limit: int, offset: int)` method using `func.to_tsquery()`
  2. Add `ts_rank()` ordering for relevance scoring
  3. Return results with rank score included
  4. Handle empty query and special characters gracefully
- **Done when:** `pytest tests/unit/test_article_repo.py::test_search -x` passes
- **Complexity:** small

### Task 3: Create search service
- **Files:** `backend/services/search_service.py`
- **Preconditions:** Task 2
- **Steps:**
  1. Create `SearchService` with `search_articles(query, page, page_size)` method
  2. Add query sanitization (strip special tsquery characters)
  3. Add pagination using cursor-based approach
  4. Return `SearchResult` with items, total_count, has_next
- **Done when:** `pytest tests/unit/test_search_service.py -x` passes
- **Complexity:** small

### Task 4: Create search endpoint
- **Files:** `backend/routes/search.py`, `backend/schemas/search.py`
- **Preconditions:** Task 3
- **Steps:**
  1. Create `SearchQuery` schema with `q`, `page`, `page_size` fields
  2. Create `SearchResponse` schema with items, total, has_next
  3. Create `GET /search/articles?q=...&page=1&page_size=20` endpoint
  4. Register router
- **Done when:** `pytest tests/integration/test_search_routes.py -x` passes
- **Complexity:** small

### Task 5: Create frontend search component
- **Files:** `frontend/src/components/SearchBar.tsx`, `frontend/src/hooks/useSearch.ts`
- **Preconditions:** Task 4
- **Steps:**
  1. Create `useSearch(query)` hook with TanStack Query, debounced input (300ms)
  2. Create `SearchBar` component with input field, loading indicator, results dropdown
  3. Add keyboard navigation (arrow keys, enter to select, escape to close)
  4. Add highlight matching text in results
- **Done when:** `npm test -- --grep "SearchBar|useSearch"` passes
- **Complexity:** medium

### Task 6: Integration test for search flow
- **Files:** `tests/integration/test_search_e2e.py`
- **Preconditions:** Task 4, Task 5
- **Steps:**
  1. Seed test database with 10 articles with known content
  2. Test search returns relevant results ranked by relevance
  3. Test empty query returns appropriate response
  4. Test pagination works correctly
  5. Test special characters don't cause errors
- **Done when:** `pytest tests/integration/test_search_e2e.py -x` passes
- **Complexity:** small

**Dependency Graph:**
```
Task 1 (migration) ──→ Task 2 (repo) ──→ Task 3 (service) ──→ Task 4 (endpoint) ──→ Task 5 (frontend)
                                                                      ↓                    ↓
                                                                 Task 6 (integration) ←────┘
```

---

## Example 3: Add File Upload with S3 Storage (7 Tasks)

**Objective:** Add file upload capability with S3 storage, file metadata tracking, and a frontend upload component with drag-and-drop.

### Task 1: Add S3 configuration and client
- **Files:** `backend/core/config.py`, `backend/services/storage_service.py`
- **Preconditions:** None
- **Steps:**
  1. Add S3 settings to config: `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_ENDPOINT`
  2. Create `StorageService` class with async methods: `upload_file()`, `delete_file()`, `generate_presigned_url()`
  3. Use `aioboto3` for async S3 operations
  4. Add configurable max file size (default 10MB) and allowed MIME types
- **Done when:** `pytest tests/unit/test_storage_service.py -x` passes (using mocked S3)
- **Complexity:** medium

### Task 2: Add File model and migration
- **Files:** `backend/models/file.py`, `backend/migrations/versions/xxxx_add_file.py`
- **Preconditions:** None (parallel with Task 1)
- **Steps:**
  1. Create `File` model with fields: id, original_name, s3_key, content_type, size_bytes, uploaded_by (FK to User), created_at
  2. Add index on `uploaded_by` for efficient user file listing
  3. Generate and run Alembic migration
- **Done when:** `alembic current` shows latest AND `SELECT * FROM files` returns empty table
- **Complexity:** small

### Task 3: Create file schemas
- **Files:** `backend/schemas/file.py`
- **Preconditions:** None (parallel with Task 1 and 2)
- **Steps:**
  1. Create `FileResponse(id, original_name, content_type, size_bytes, download_url, created_at)` schema
  2. Create `FileListResponse(items: list[FileResponse], total: int)` schema
  3. Add content_type validation against allowed MIME types
- **Done when:** `python -c "from backend.schemas.file import FileResponse, FileListResponse"` succeeds
- **Complexity:** trivial

### Task 4: Create file service
- **Files:** `backend/services/file_service.py`
- **Preconditions:** Task 1, Task 2, Task 3
- **Steps:**
  1. Create `FileService` with methods: `upload(file, user_id)`, `delete(file_id, user_id)`, `list_user_files(user_id)`, `get_download_url(file_id)`
  2. Validate file size and MIME type before upload
  3. Generate unique S3 key using UUID + original extension
  4. Save metadata to database after successful S3 upload
  5. Delete from both S3 and database on delete
- **Done when:** `pytest tests/unit/test_file_service.py -x` passes
- **Complexity:** medium

### Task 5: Create file upload/download routes
- **Files:** `backend/routes/files.py`
- **Preconditions:** Task 4
- **Steps:**
  1. Create `POST /files/upload` endpoint accepting `UploadFile` with auth dependency
  2. Create `GET /files` endpoint listing user's files with pagination
  3. Create `GET /files/{file_id}/download` endpoint returning presigned URL redirect
  4. Create `DELETE /files/{file_id}` endpoint with ownership check
  5. Register router
- **Done when:** `pytest tests/integration/test_file_routes.py -x` passes
- **Complexity:** medium

### Task 6: Create frontend upload component
- **Files:** `frontend/src/components/FileUpload.tsx`, `frontend/src/hooks/useFileUpload.ts`
- **Preconditions:** Task 5
- **Steps:**
  1. Create `useFileUpload()` hook with TanStack Query mutation, progress tracking, error handling
  2. Create `FileUpload` component with drag-and-drop zone, file type validation, size display
  3. Show upload progress bar during upload
  4. Display uploaded files list with download and delete actions
  5. Add accessible labels and keyboard support for drag-and-drop area
- **Done when:** `npm test -- --grep "FileUpload|useFileUpload"` passes
- **Complexity:** medium

### Task 7: Integration test for upload flow
- **Files:** `tests/integration/test_file_upload_e2e.py`
- **Preconditions:** Task 5, Task 6
- **Steps:**
  1. Test upload with valid file succeeds and returns file metadata
  2. Test upload with oversized file returns 413
  3. Test upload with disallowed MIME type returns 422
  4. Test file listing returns only authenticated user's files
  5. Test download generates valid presigned URL
  6. Test delete removes file from both S3 and database
- **Done when:** `pytest tests/integration/test_file_upload_e2e.py -x` passes
- **Complexity:** small

**Dependency Graph:**
```
Task 1 (S3 client) ───→ Task 4 (service) ──→ Task 5 (routes) ──→ Task 6 (frontend)
                              ↑                     ↓                    ↓
Task 2 (model) ──────────────┘                Task 7 (integration) ←────┘
                              ↑
Task 3 (schemas) ────────────┘
```

---

## Example 4: Add Real-Time Notifications (7 Tasks)

**Objective:** Add real-time notification system using WebSockets with database-backed notification storage and a frontend notification center.

### Task 1: Add Notification model and migration
- **Files:** `backend/models/notification.py`, `backend/migrations/versions/xxxx_add_notification.py`
- **Preconditions:** None
- **Steps:**
  1. Create `Notification` model with fields: id, user_id (FK), type (enum), title, body, is_read, created_at
  2. Create `NotificationType` enum: `info`, `warning`, `success`, `error`
  3. Add composite index on `(user_id, is_read, created_at)` for efficient unread queries
  4. Generate and run migration
- **Done when:** `alembic current` shows latest AND table exists with correct columns
- **Complexity:** small

### Task 2: Create notification schemas
- **Files:** `backend/schemas/notification.py`
- **Preconditions:** None (parallel with Task 1)
- **Steps:**
  1. Create `NotificationResponse(id, type, title, body, is_read, created_at)` schema
  2. Create `NotificationListResponse(items, unread_count, total)` schema
  3. Create `NotificationCreate(user_id, type, title, body)` for internal use
- **Done when:** `python -c "from backend.schemas.notification import NotificationResponse"` succeeds
- **Complexity:** trivial

### Task 3: Create notification service
- **Files:** `backend/services/notification_service.py`
- **Preconditions:** Task 1, Task 2
- **Steps:**
  1. Create `NotificationService` with: `create(user_id, type, title, body)`, `list_for_user(user_id, unread_only)`, `mark_read(notification_id, user_id)`, `mark_all_read(user_id)`
  2. Add `get_unread_count(user_id)` for badge display
  3. All methods use async SQLAlchemy session
- **Done when:** `pytest tests/unit/test_notification_service.py -x` passes
- **Complexity:** small

### Task 4: Create WebSocket connection manager
- **Files:** `backend/services/ws_manager.py`
- **Preconditions:** None (parallel with Tasks 1-3)
- **Steps:**
  1. Create `ConnectionManager` class maintaining `dict[int, list[WebSocket]]` (user_id to connections)
  2. Add methods: `connect(user_id, websocket)`, `disconnect(user_id, websocket)`, `send_to_user(user_id, message)`
  3. Handle connection cleanup on disconnect
  4. Support multiple connections per user (multiple browser tabs)
- **Done when:** `pytest tests/unit/test_ws_manager.py -x` passes
- **Complexity:** small

### Task 5: Create notification routes (REST + WebSocket)
- **Files:** `backend/routes/notifications.py`
- **Preconditions:** Task 3, Task 4
- **Steps:**
  1. Create `GET /notifications` with optional `unread_only` query param
  2. Create `PATCH /notifications/{id}/read` to mark single as read
  3. Create `PATCH /notifications/read-all` to mark all as read
  4. Create `WS /notifications/ws` WebSocket endpoint with JWT auth
  5. Register both REST and WebSocket routes
- **Done when:** `pytest tests/integration/test_notification_routes.py -x` passes
- **Complexity:** medium

### Task 6: Create frontend notification hooks and components
- **Files:** `frontend/src/hooks/useNotifications.ts`, `frontend/src/components/NotificationCenter.tsx`
- **Preconditions:** Task 5
- **Steps:**
  1. Create `useNotifications()` hook: WebSocket connection, reconnection logic, notification state
  2. Create `useNotificationActions()` hook: markRead, markAllRead mutations
  3. Create `NotificationCenter` component: bell icon with unread badge, dropdown panel, notification list
  4. Add sound/visual indicator for new notifications
  5. Add accessible announcements for screen readers on new notifications
- **Done when:** `npm test -- --grep "NotificationCenter|useNotifications"` passes
- **Complexity:** medium

### Task 7: Integration test for notification flow
- **Files:** `tests/integration/test_notifications_e2e.py`
- **Preconditions:** Task 5, Task 6
- **Steps:**
  1. Test creating a notification delivers it via WebSocket to connected user
  2. Test notification persists in database and appears in REST list
  3. Test mark-read updates both database and unread count
  4. Test mark-all-read clears all unread for user
  5. Test WebSocket reconnection after disconnect
- **Done when:** `pytest tests/integration/test_notifications_e2e.py -x` passes
- **Complexity:** small

**Dependency Graph:**
```
Task 1 (model) ──→ Task 3 (service) ──→ Task 5 (routes) ──→ Task 6 (frontend)
                        ↑                     ↑                    ↓
Task 2 (schemas) ──────┘                      │              Task 7 (integration)
                                              │
Task 4 (WS manager) ────────────────────────┘
```

---

## Decomposition Checklist

After creating your task plan, verify against this checklist:

- [ ] Every task touches at most 2-3 files
- [ ] Every task has a single clear outcome
- [ ] Every task has a concrete verification command
- [ ] Every task lists its preconditions by task ID
- [ ] No task exceeds 200 lines of changes
- [ ] No circular dependencies exist in the graph
- [ ] Infrastructure/migration tasks come before code that depends on them
- [ ] Backend tasks come before frontend tasks that consume the API
- [ ] Shared types/schemas are available before both layers use them
- [ ] Tests are included for each layer
- [ ] Persistent task files (task_plan.md, progress.md) are created
