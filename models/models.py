from datetime import datetime
from extensions import db

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    quizzes = db.relationship('Quiz', backref='teacher', lazy=True, cascade='all, delete-orphan')

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    token = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    time_limit = db.Column(db.Integer, nullable=False)
    shuffle_questions = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='quiz', lazy=True, cascade='all, delete-orphan')
    show_answers = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    text = db.Column(db.String(600), nullable=False)
    image_path = db.Column(db.String(300), nullable=True)
    option1 = db.Column(db.String(300), nullable=False)
    option2 = db.Column(db.String(300), nullable=False)
    option3 = db.Column(db.String(300), nullable=False)
    option4 = db.Column(db.String(300), nullable=False)
    correct = db.Column(db.SmallInteger, nullable=False)
    score = db.Column(db.Float, default=1.0)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    class_no = db.Column(db.String(30), nullable=False)
    question_order = db.Column(db.Text, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.now)
    submitted_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    warnings = db.Column(db.Integer, default=0)
    answers = db.relationship('Answer', backref='submission', lazy=True, cascade='all, delete-orphan')
    warning_logs = db.relationship('WarningLog', backref='submission', lazy=True, cascade='all, delete-orphan')

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected = db.Column(db.SmallInteger, default=0)
    is_correct = db.Column(db.Boolean, default=False)
    question = db.relationship('Question', lazy=True)

class WarningLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
