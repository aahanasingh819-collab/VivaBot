# VivaBot

VivaBot helps students practise project vivas using questions grounded in their uploaded project report. It is a Django application with Django REST Framework endpoints, server-rendered templates, SQLite development storage, and server-side Google Gemini calls.

## Requirements

- Python 3.10 or newer
- A Google AI Studio API key for real question generation and answer evaluation

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Generate a local Django signing key and place it in `.env` as `SESSION_SECRET`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Set `GOOGLE_API_KEY` in `.env` for local development. Do not commit `.env`; the repository ignores it. In Replit, configure `GOOGLE_API_KEY` and `SESSION_SECRET` using Replit Secrets instead. Neither value is sent to the browser.

Initialize the SQLite database and start the app:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Open the site at `http://127.0.0.1:8000/`. In Replit, use the VivaBot web preview. Development media files are stored in the ignored `media/` directory.

## Run checks and tests

```bash
python manage.py check
python manage.py test
```

The tests mock Gemini responses and do not call the live API. To use a different Gemini model, set `GEMINI_MODEL`; the default is `gemini-2.5-flash`.

## Student workflow

1. Create an account and sign in.
2. Add a project description, technologies, and a PDF, TXT, or DOCX report (up to 10 MB).
3. Generate a viva at the desired difficulty.
4. Answer questions one at a time and review the AI-generated evaluation.
5. Finish the viva to save an overall score and question-by-question feedback.
6. Revisit sessions from Dashboard, Project details, or History.

Report uploads are text-extracted on the server and private to the owning account. Uploaded files are not served from a public media URL; report downloads go through an authenticated, owner-checked view. The extracted text is stored with the project and bounded before being sent to Gemini.

## REST API

The API uses Django session authentication and CSRF protection. Private routes require a signed-in user and scope project, viva, and question queries to that user's records.

- `GET /vivabot-api/projects/`
- `POST /vivabot-api/projects/`
- `GET /vivabot-api/projects/<id>/`
- `PATCH /vivabot-api/projects/<id>/`
- `DELETE /vivabot-api/projects/<id>/`
- `POST /vivabot-api/projects/<id>/vivas/` — generate and save a new report-specific viva
- `GET /vivabot-api/vivas/`
- `GET /vivabot-api/vivas/<id>/`
- `GET /vivabot-api/vivas/<id>/result/` — completed sessions only
- `POST /vivabot-api/questions/<id>/answer/`

Project creation expects multipart form data with `title`, `description`, and `report_file`; `technologies_used` is optional. Answer submission expects JSON such as `{"answer_text":"..."}`.

## Configuration and security

- Replit uses the `SESSION_SECRET` and `GOOGLE_API_KEY` secrets for Django signing and Gemini access.
- Local development can use `.env`; use `.env.example` as a variable-name reference only.
- `DJANGO_DEBUG` defaults to `false`. Set it to `true` only for local development.
- Production hosts can be specified through `ALLOWED_HOSTS`; Replit host environment values are also recognized.
- Gemini credentials are used only by `viva/services/gemini_service.py`.
- If the Gemini key is missing or a response is invalid, VivaBot displays a controlled error and does not save partial questions or evaluations.