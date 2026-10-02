# VivaBot

VivaBot helps students practise project vivas with questions grounded in their report and saved feedback for each answer.

## Run & Operate

- `python manage.py check` — validate Django configuration
- `python manage.py test` — run the web, API, ownership, and mocked-Gemini tests
- `python manage.py migrate` — apply SQLite migrations
- `python manage.py collectstatic --noinput` — prepare static files for WhiteNoise
- Required Replit Secrets: `SESSION_SECRET`, `GOOGLE_API_KEY`
- Main app: standalone Django workflow on port 8000; API and Canvas workflows belong to the existing artifacts

## Stack

- Python 3.12, Django, Django REST Framework
- Server-rendered Django templates with vanilla JavaScript and responsive CSS
- SQLite for development, with private report files on local storage
- Google Gemini via the official Google GenAI SDK; credentials remain server-side

## Where things live

- `config/` — Django settings, URL configuration, and WSGI/ASGI entry points
- `users/` — registration, login, and account/profile views
- `projects/` — project and report models, upload parsing/validation, owner-scoped pages
- `viva/` — viva models, Gemini calls, saved evaluations, practice and results views
- `api/` — DRF serializers, owner permissions, project/viva endpoints, and tests
- `templates/` and `static/` — responsive HTML, CSS, and progressive-enhancement JavaScript
- `README.md` — local setup, environment configuration, student workflow, and API reference

## Architecture decisions

- Django's built-in authentication backs both private pages and DRF session authentication.
- Reports are downloaded through an authenticated owner-checked view; there is no public media route.
- Gemini receives bounded extracted report context; JSON is validated before questions or evaluations are saved.
- Viva answer text and its evaluation are committed together, and duplicate submissions reuse the saved evaluation.

## Product

Users can create projects with PDF, DOCX, or TXT reports, practise one viva question at a time, review answer-level feedback and final scores, and revisit history. Admin is available at `/admin/`.

## User preferences

Keep the requested stack: Python, Django, DRF, Django templates, and vanilla JavaScript. Do not replace it with React or Node.

## Gotchas

- Use Replit Secrets for `GOOGLE_API_KEY` and `SESSION_SECRET`; never expose either in templates or API responses.
- Gemini-dependent tests mock the provider and must not issue billable live requests.
- When changing project fields or viva models, create and commit Django migrations.

## Pointers

- See `README.md` for first-time setup and endpoint details.
