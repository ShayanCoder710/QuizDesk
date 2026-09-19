# QuizDesk

An online quiz platform for teachers. Create multiple-choice quizzes, share links with students, and track results — no student signup required.

## Features

- Create quizzes with up to 200 questions
- Randomize question order to prevent cheating
- Timer with auto-submit
- Tab-switch warnings for proctoring
- Image support per question
- Export results as PDF
- Persian (Farsi) UI

## Tech Stack

- **Backend:** Python 3.13 + Flask
- **Database:** MySQL (SQLAlchemy ORM)
- **PDF:** WeasyPrint
- **Calendar:** jdatetime (Persian Jalali dates)
- **Security:** Flask-WTF CSRF protection, bcrypt-style password hashing

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Configure database
# Edit config.py with your MySQL credentials

# Run
python app.py
```
