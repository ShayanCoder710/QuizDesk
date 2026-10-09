import json
import os
import random
import secrets
import hashlib
import hmac
from pathlib import Path
from datetime import datetime, timedelta
import jdatetime
from flask import session, flash, redirect, url_for, abort, current_app
from extensions import db
from models.models import Teacher, Quiz, Submission, Question, Answer, WarningLog

def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f'{salt}${hashed}'

def verify_password(password, stored):
    try:
        salt, hashed = stored.split('$', 1)
    except ValueError:
        return False
    candidate = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return hmac.compare_digest(candidate, hashed)

def owned_quiz_or_404(token):
    quiz = Quiz.query.filter_by(token=token).first_or_404()
    if quiz.teacher_id != session.get('teacher_id'):
        abort(403)
    return quiz

def get_take(token):
    quiz = Quiz.query.filter_by(token=token).first()
    if not quiz:
        return None, None
    sid = session.get(f'take_{token}')
    sub = db.session.get(Submission, sid) if sid else None
    if sub and sub.quiz_id != quiz.id:
        sub = None
    return quiz, sub

def order_of(sub):
    try:
        return json.loads(sub.question_order or '[]')
    except (TypeError, ValueError):
        return []

def finalize_submission(sub, form_data):
    quiz = db.session.get(Quiz, sub.quiz_id)
    qids = order_of(sub)
    qmap = {q.id: q for q in quiz.questions}

    Answer.query.filter_by(submission_id=sub.id).delete()
    
    total_score = 0.0
    max_score = 0.0
    
    for qid in qids:
        q = qmap.get(qid)
        if not q:
            continue
        
        max_score += float(q.score)
        
        selected = None
        if form_data:
            raw = form_data.get(f'answer_{qid}') or form_data.get(f'q_{qid}')
            if raw and str(raw).strip().isdigit():
                selected = int(raw)
        
        is_correct = (selected == q.correct) if selected else False
        if is_correct:
            total_score += float(q.score)
        
        db.session.add(Answer(
            submission_id=sub.id,
            question_id=qid,
            selected=selected,
            is_correct=is_correct
        ))
    
    sub.score = round(total_score, 4)
    sub.total = round(max_score, 4)
    sub.submitted_at = datetime.now()
    db.session.commit()

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

def fa_filter(value):
    return ''.join(FA_DIGITS[int(ch)] if ch.isdigit() else ch for ch in str(value))

PERSIAN_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
def jdate_filter(value):
    if not value:
        return '—'
    jdt = jdatetime.datetime.fromgregorian(datetime=value)
    month_name = PERSIAN_MONTHS[jdt.month - 1]
    return f"{fa_filter(jdt.day)} {month_name} {fa_filter(jdt.year)} — {fa_filter(jdt.strftime('%H:%M'))}"

def jtime_filter(value):
    if not value:
        return '—'
    jdt = jdatetime.datetime.fromgregorian(datetime=value)
    return fa_filter(jdt.strftime('%H:%M:%S'))

def font_file_url(filename):
    path = os.path.abspath(os.path.join(current_app.root_path, 'static', 'fonts', filename))
    return Path(path).as_uri()

FA_TO_ASCII = {ch: str(i) for i, ch in enumerate(FA_DIGITS)}
FA_TO_ASCII.update({'٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9'})

def fa_to_ascii(text):
    if not text:
        return ''
    return ''.join(FA_TO_ASCII.get(ch, ch) for ch in str(text))

def to_int(text, default=None):
    t = fa_to_ascii(str(text)).strip()
    if not t:
        return default
    try:
        return int(t)
    except ValueError:
        return default

def to_float(text, default=None):
    t = fa_to_ascii(str(text)).strip()
    if not t:
        return default
    try:
        return float(t)
    except ValueError:
        return default

def jalali_to_gregorian(y, m, d):
    return jdatetime.datetime(int(y), int(m), int(d)).togregorian()

def parse_jalali_date(text):
    if not text:
        return None
    t = fa_to_ascii(str(text)).strip()
    parts = [p for p in t.replace('/', ' ').replace('-', ' ').split() if p]
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    try:
        return jalali_to_gregorian(y, m, d)
    except (ValueError, OverflowError):
        return None
