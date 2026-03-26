from .base import TestTemplate, register_template

register_template(TestTemplate(
    name="api",
    description="Express REST API with TypeScript, validation, and Jest tests",
    prompt="""Build a REST API using Express + TypeScript.

Requirements:
1. Initialize a Node.js project with TypeScript
2. Install express, zod (for validation), and their type definitions
3. Create a `/tasks` resource with the following endpoints:
   - `GET /tasks` — return all tasks (in-memory array)
   - `POST /tasks` — create a task; body: `{ title: string (required, min 3 chars), done?: boolean }`
   - `GET /tasks/:id` — return a task by ID; 404 if not found
   - `PATCH /tasks/:id` — update title or done; 404 if not found
   - `DELETE /tasks/:id` — delete a task; 404 if not found
4. Validate all request bodies using Zod. Return `400` with a clear error message on invalid input.
5. Tasks have: `id` (auto-increment integer), `title` (string), `done` (boolean, default false), `createdAt` (ISO string)
6. Add at least 6 Jest tests covering: create, list, get-by-id, update, delete, and validation error
7. `npm run build` must compile without TypeScript errors
8. `npm test` must run and pass all tests

Do not use a database — in-memory storage is fine. Write the complete, working API and tests.""",
    acceptance_criteria=[
        "npm run build compiles without errors",
        "GET /tasks returns array",
        "POST /tasks creates a task with auto-generated id and createdAt",
        "GET /tasks/:id returns 404 for unknown ID",
        "PATCH /tasks/:id updates fields and returns 404 for unknown ID",
        "DELETE /tasks/:id removes task and returns 404 for unknown ID",
        "POST /tasks with missing or short title returns 400",
        "All Jest tests pass (npm test)",
    ],
))
