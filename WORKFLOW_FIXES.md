# Workflow fixes

## Database setup

SQLite remains the default. Setting `DB_HOST` selects PostgreSQL, using
`DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_PORT`. The existing Docker Compose
configuration already provides these variables. Install `requirements.txt` in
the deployment environment before switching databases.

Run `python manage.py migrate` before serving the updated application.
The new dashboard migration stores notification receipts per user so signing
out or using another browser does not replay notifications already viewed.
Only the six notifications actually rendered in the panel are marked read.
The ticket migration approves previously pending private text-only messages
and routes eligible tickets to their assigned consultant. It leaves pending
attachments, rejected messages, internal notes, and closed ticket queues alone.

Enrollment serializes capacity checks with a write before reading the course
and uses an outer, non-distinct row-locking query for PostgreSQL. Unique
enrollment and notification constraints make repeated requests idempotent.
Question performance uses filtered counts rather than sums of Boolean fields,
and aggregates by subject instead of querying every subject separately.
Consultant ticket lists use database-side existence checks rather than loading
all candidate tickets and querying each scope individually.

## Permissions and moderation

- Assigned consultants can create quizzes for their assigned students without
  a separate general quiz permission. General quiz access retains the broader
  audience selector; assignment-only access cannot select unrelated students.
- Trustees can review global courses and courses targeting their province.
  Approval is also available directly on the course detail page.
- Administrators, trustees, consultants, and content moderators can preview
  course content without creating a student enrollment.
- Private text messages are immediately visible to the assigned consultant;
  attachments remain hidden from the recipient until moderator approval.
  Existing ticket gender restrictions are preserved.

## Verification

Run the focused regressions with:

```text
python manage.py test dashboard_module.test_workflow_regressions --noinput
```

Run this command against each configured database separately. PostgreSQL must
be available and its test user must have permission to create a test database.

Local validation uses SQLite; no PostgreSQL server was available for testing
in the current environment. The dashboard, ticketing, and counseling suites
pass the focused regression suites. The notification
JavaScript also passes a simulated open/close and single-read-request check.
The broader pre-existing suite also contains stale
question fixtures using removed `code` fields and unrelated course-media and
quiz-page/result expectations. These are outside this patch's regression scope.

## Counseling, question submission, and dashboard updates

- Administrators and province trustees can assign a consultant to multiple
  checked students in one atomic request. Both the selected students and the
  active consultant are validated; trustees cannot submit out-of-province IDs.
- Superusers see consultant assignment rather than the student-only
  "my consultant" link, even when their stored role defaults to STUDENT.
- Consultants can submit questions without a separate bank-reading permission.
  Submissions remain inactive and pending until the relevant regional reviewer
  approves them. Approval still controls bank and quiz availability.
- Ticket lists, message threads, creation, private counseling, and moderation
  share a responsive glass theme. List search, scoped counters, and pagination
  preserve existing access restrictions.
- Student dashboards display date-specific tomorrow plans, live/upcoming
  classes, and eligible online quizzes. Old weeks no longer appear as today's
  work. New personal and staff plans initially use today's local date.
- Quiz navigation indicators use approved, unpaused quizzes available to the
  individual student, excluding closed quizzes and exhausted attempts. Their
  existing start/end windows are checked in the browser every 15 seconds on
  every page; future starts do not require a page reload.

## Curriculum migration safety

Back up the database before running `python manage.py migrate`.
Migration users_module.0008 normalizes Persian/Arabic letter variants and
whitespace, merges duplicate grades within each school and duplicate fields
within each grade, and preserves related students, subjects, quiz targeting,
and course many-to-many memberships. Identical titles in different schools
or grades remain separate because they represent distinct academic scopes.
This data merge cannot reconstruct the original duplicate IDs when reversed.
Migration 0009 adds database uniqueness constraints after the data transaction
has committed, avoiding PostgreSQL deferred-trigger/schema-change conflicts.

Run the expanded regressions with:

```text
python manage.py test dashboard_module counseling_module ticketing_module plans_module --noinput
```

The new feature tests include an actual migration rollback/forward test with
linked academic, student, course, and quiz data. SQLite is exercised locally.
The earlier focused run passes 87 tests, including 19 feature/migration tests;
`makemigrations --check --dry-run` reports no missing migrations.
The quiz audience query also compiles successfully using Django's PostgreSQL
backend; this is not a substitute for running the suite against a real
PostgreSQL server. The browser-side indicator passes simulated active,
expiry, future-start, and exact end-boundary checks.

## Academic spreadsheets and publication scheduling

- The admin navigation now includes separate grade, field, and subject Excel
  uploads at `/users/curriculum/import/`, with downloadable templates and
  per-row results. CSV is also supported. Imports reuse existing titles.
- Each row can specify province, school, grade and field. Empty cells use the
  form defaults. A one-column file requires a school/default academic scope,
  or explicit permission to apply it across the selected province/all schools.
  Import grades first, then fields, then subjects.
- Member imports accept `کلاس` as a grade header, numeric Persian/English grades,
  common field aliases, numeric/scientific Excel national codes, shared strings
  and actual worksheet row numbers. Missing roles default to student; blank
  fields are inferred only when the chosen grade has one field. Invalid rows
  roll back without leaving a partial user. Existing members are not overwritten.
- Course and quiz selectors show each academic title once. Course selections
  retain all school-specific targets, and quiz audience matching uses titles
  while preserving school/province restrictions. Hierarchical forms narrow
  grade/field options by school rather than presenting repeated names.
- Course scheduling uses separated responsive controls, LTR Jalali datetime
  input, explicit time selection, normalized digits and server-side validation.
- Users migrations 0010 and 0011 merge normalized province, school and subject
  duplicates before adding database constraints. Nested questions, student
  references, trustee assignments and course memberships are preserved. Genuine
  school-specific academic records are not deleted just because titles match.
- Query grouping uses portable `MIN` subqueries, not PostgreSQL-only `DISTINCT ON`.
  PostgreSQL compilation is checked offline; a live PostgreSQL test database
  is not available in this environment.

Validation on October 16, 2026: 119 focused regression tests passed, followed
by all 23 academic spreadsheet tests after adding real numeric/shared-string
Excel and duplicate trustee migration coverage. JavaScript syntax checks and
`makemigrations --check --dry-run` passed. The existing CKEditor warning remains.
The local SQLite database was backed up with an integrity-checked SQLite backup
to `.local-backups/before-academic-fixes-20261016-173914.sqlite3`, and migrations
users_module.0008 through 0011 were applied successfully. Backups are gitignored.
