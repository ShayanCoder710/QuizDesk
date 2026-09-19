from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory, Response
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFError
from config import MYSQL_CONFIG, SECRET_KEY
from extensions import db, csrf
from models.models import Teacher, Quiz, Submission, Question, Answer, WarningLog
import func
import secrets, random, json, os
from datetime import datetime
from weasyprint import HTML
import shutil

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def image_size(file_storage):
    """Return the byte size of an uploaded file, rewinding the stream afterwards."""
    try:
        if not file_storage or not file_storage.stream:
            return 0
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        return size
    except Exception:
        return 0

def save_question_image(file, token, q_index):
    if file and allowed_file(file.filename):
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{token}_q{q_index}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return filename
    return None

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = MYSQL_CONFIG
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db.init_app(app)
csrf.init_app(app)

app.add_template_filter(func.fa_filter, 'fa')
app.add_template_filter(func.jdate_filter, 'jdate')
app.add_template_filter(func.jtime_filter, 'jtime')

@app.route('/')
def index():
    if session.get('teacher_id'):
        return redirect(url_for('panel'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('teacher_id'):
        return redirect(url_for('panel'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        errors = []
        if not (2 <= len(name) <= 80):
            errors.append('نام باید بین ۲ تا ۸۰ حرف باشد.')
        if not (3 <= len(username) <= 32):
            errors.append('نام کاربری باید بین ۳ تا ۳۲ حرف باشد.')
        if len(password) < 6:
            errors.append('رمز عبور باید حداقل ۶ حرف باشد.')
        if password != confirm:
            errors.append('تکرار رمز عبور یکسان نیست.')
        if not errors and Teacher.query.filter_by(username=username).first():
            errors.append('این نام کاربری قبلاً ثبت شده است.')
        if errors:
            for err in errors:
                flash(err, 'err')
        else:
            teacher = Teacher(name=name, username=username, password_hash=func.hash_password(password))
            db.session.add(teacher)
            db.session.commit()
            flash('حساب شما با موفقیت ساخته شد.', 'ok')
            return redirect(url_for('login'))
    return render_template('register.html')

ADMIN_USERNAME = 'shayan'
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('teacher_id'):
        return redirect(url_for('panel'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        teacher = Teacher.query.filter_by(username=username).first()
        if teacher and func.verify_password(password, teacher.password_hash):
            session['teacher_id'] = teacher.id
            session['teacher_name'] = teacher.name
            session['teacher_username'] = teacher.username
            flash(f'{teacher.name} عزیز، خوش آمدید 👋', 'ok')
            return redirect(url_for('panel'))
        flash('نام کاربری یا رمز عبور اشتباه است.', 'err')
    return render_template('login.html')


@app.route('/admin')
def admin_panel():
    if session.get('teacher_username') != ADMIN_USERNAME:
        abort(403)
    
    teachers = Teacher.query.all()
    quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
    total_submissions = Submission.query.filter(Submission.submitted_at.isnot(None)).count()
    
    return render_template('admin.html', teachers=teachers, quizzes=quizzes, total_submissions=total_submissions, admin_username=ADMIN_USERNAME)


@app.route('/admin/quiz/<token>')
def admin_view_quiz(token):
    if session.get('teacher_username') != ADMIN_USERNAME:
        abort(403)
    
    quiz = Quiz.query.filter_by(token=token).first_or_404()
    done = [s for s in quiz.submissions if s.submitted_at]
    return render_template('admin_quiz_detail.html', quiz=quiz, done_count=len(done))


@app.route('/admin/delete_teacher/<int:teacher_id>', methods=['POST'])
def admin_delete_teacher(teacher_id):
    if session.get('teacher_username') != ADMIN_USERNAME:
        abort(403)
    
    teacher = db.session.get(Teacher, teacher_id)
    if teacher:
        for quiz in teacher.quizzes:
            for q in quiz.questions:
                if q.image_path:
                    filepath = os.path.join(UPLOAD_FOLDER, q.image_path)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
            db.session.delete(quiz)
        db.session.delete(teacher)
        db.session.commit()
        flash('کاربر و تمام آزمون‌های مرتبط با موفقیت حذف شد.', 'ok')
    
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete_quiz/<token>', methods=['POST'])
def admin_delete_quiz(token):
    if session.get('teacher_username') != ADMIN_USERNAME:
        abort(403)
    
    quiz = Quiz.query.filter_by(token=token).first_or_404()
    for q in quiz.questions:
        if q.image_path:
            filepath = os.path.join(UPLOAD_FOLDER, q.image_path)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    db.session.delete(quiz)
    db.session.commit()
    flash('آزمون با موفقیت حذف شد.', 'ok')
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    flash('با موفقیت خارج شدید.', 'ok')
    return redirect(url_for('login'))


@app.route('/panel')
def panel():
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    teacher = db.session.get(Teacher, session['teacher_id'])
    quizzes = Quiz.query.filter_by(teacher_id=teacher.id).order_by(Quiz.created_at.desc()).all()
    total_students = sum(len([s for s in q.submissions if s.submitted_at]) for q in quizzes)
    total_questions = sum(len(q.questions) for q in quizzes)
    return render_template('panel.html', teacher=teacher, quizzes=quizzes, total_students=total_students, total_questions=total_questions)


@app.route('/quiz/new', methods=['GET', 'POST'])
def create_quiz():
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    if request.method == 'POST':
        if not request.form.get('csrf_token'):
            flash('خطای اعتبارسنجی امنیتی. لطفاً صفحه را رفرش کنید.', 'err')
            return render_template('create_quiz.html', quiz=None, questions_data=None, prefill={
                'title': '', 'time_limit': '', 'shuffle': False, 'show_answers': False,
            }), 400
        
        title = request.form.get('title', '').strip()
        raw_time = request.form.get('time_limit', '').strip()
        shuffle = 'shuffle' in request.form
        show_answers = 'show_answers' in request.form
        errors = []
        
        if not title or len(title) > 150:
            errors.append('نام آزمون الزامی است و باید حداکثر ۱۵۰ حرف باشد.')
        try:
            minutes = int(raw_time)
            if not (1 <= minutes <= 480):
                errors.append('زمان آزمون باید بین ۱ تا ۴۸۰ دقیقه باشد.')
        except ValueError:
            minutes = 0
            errors.append('زمان آزمون معتبر نیست.')
        try:
            count = int(request.form.get('question_count', '0'))
        except ValueError:
            count = 0
        if not (1 <= count <= 200):
            errors.append('حداقل ۱ و حداکثر ۲۰۰ سوال می‌توان ساخت.')
            
        questions = []
        redisplay = []
        for i in range(count):
            text = request.form.get(f'q{i}_text', '').strip()
            opts = [request.form.get(f'q{i}_opt{j}', '').strip() for j in range(1, 5)]
            correct_raw = request.form.get(f'q{i}_correct', '')
            score_raw = request.form.get(f'q{i}_score', '1').strip()
            image_file = request.files.get(f'q{i}_image')
            ok = True
            
            if not text or len(text) > 600:
                errors.append(f'سوال {i + 1}: متن سوال را کامل بنویسید.')
                ok = False
            if any((not o) or len(o) > 300 for o in opts):
                errors.append(f'سوال {i + 1}: هر چهار گزینه را کامل بنویسید.')
                ok = False
            if correct_raw not in ('1', '2', '3', '4'):
                errors.append(f'سوال {i + 1}: گزینه صحیح را مشخص کنید.')
                ok = False
            try:
                score = float(score_raw)
                if not (0 <= score <= 100):
                    errors.append(f'سوال {i + 1}: نمره باید بین ۰ تا ۱۰۰ باشد.')
                    ok = False
            except ValueError:
                score = None
                errors.append(f'سوال {i + 1}: نمره معتبر نیست.')
                ok = False
            if image_file and image_file.filename:
                if not allowed_file(image_file.filename):
                    errors.append(f'سوال {i + 1}: فرمت تصویر مجاز نیست (PNG, JPG, WEBP, GIF).')
                    ok = False
                elif image_size(image_file) > MAX_IMAGE_SIZE:
                    errors.append(f'سوال {i + 1}: حجم تصویر نباید بیشتر از ۵ مگابایت باشد.')
                    ok = False
            
            redisplay.append({
                'id': '', 'text': text, 'image_path': None,
                'option1': opts[0], 'option2': opts[1],
                'option3': opts[2], 'option4': opts[3],
                'correct': int(correct_raw) if correct_raw in ('1', '2', '3', '4') else None,
                'score': score if score is not None else score_raw,
            })
            if ok:
                questions.append((text, opts, int(correct_raw), score))
                
        if errors:
            for e in errors:
                flash(e, 'err')
            return render_template(
                'create_quiz.html',
                quiz=None,
                questions_data=redisplay,
                prefill={
                    'title': title,
                    'time_limit': raw_time,
                    'shuffle': shuffle,
                    'show_answers': show_answers,
                }
            )
        else:
            quiz = Quiz(teacher_id=session['teacher_id'], token=secrets.token_urlsafe(10), title=title, time_limit=minutes, shuffle_questions=shuffle, show_answers=show_answers)
            db.session.add(quiz)
            db.session.flush()
            
            for i, (text, opts, correct, score) in enumerate(questions):
                image_file = request.files.get(f'q{i}_image')
                image_path = save_question_image(image_file, quiz.token, i)
                
                db.session.add(Question(
                    quiz_id=quiz.id, text=text, image_path=image_path,
                    option1=opts[0], option2=opts[1], option3=opts[2], option4=opts[3],
                    correct=correct, score=score
                ))

            db.session.commit()
            flash('آزمون با موفقیت ساخته شد ✅ لینک آزمون آماده است.', 'ok')
            return redirect(url_for('quiz_detail', token=quiz.token))
            
    return render_template('create_quiz.html', quiz=None, questions_data=None, prefill={
        'title': '', 'time_limit': '', 'shuffle': False, 'show_answers': False,
    })


@app.route('/teacher/quiz/<token>/edit', methods=['GET', 'POST'])
def edit_quiz(token):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    
    quiz = func.owned_quiz_or_404(token)
    
    if quiz.submissions:
        flash('این آزمون قبلاً توسط دانش‌آموزان شرکت شده است. برای حفظ یکپارچگی نمرات و پاسخ‌ها، ویرایش سوالات امکان‌پذیر نیست. لطفاً یک آزمون جدید بسازید.', 'err')
        return redirect(url_for('quiz_detail', token=quiz.token))
    
    if request.method == 'POST':
        errors = []
        title = request.form.get('title', '').strip()
        if not title or len(title) > 150:
            errors.append('نام آزمون الزامی است و باید حداکثر ۱۵۰ حرف باشد.')
        try:
            minutes = int(request.form.get('time_limit', '').strip())
            if not 1 <= minutes <= 480:
                raise ValueError
        except (TypeError, ValueError):
            minutes = quiz.time_limit
            errors.append('زمان آزمون باید بین ۱ تا ۴۸۰ دقیقه باشد.')
        try:
            question_count = int(request.form.get('question_count', '0'))
        except ValueError:
            question_count = 0
        if not 1 <= question_count <= 200:
            errors.append('حداقل ۱ و حداکثر ۲۰۰ سوال می‌توان ساخت.')
        old_questions = {q.id: q for q in Question.query.filter_by(quiz_id=quiz.id).all()}
        parsed = []
        redisplay = []
        for i in range(question_count):
            text = request.form.get(f'q{i}_text', '').strip()
            opts = [request.form.get(f'q{i}_opt{j}', '').strip() for j in range(1, 5)]
            correct_raw = request.form.get(f'q{i}_correct', '')
            score_raw = request.form.get(f'q{i}_score', '1').strip()
            old_id = request.form.get(f'q{i}_id', '').strip()
            image_file = request.files.get(f'q{i}_image')
            old = old_questions.get(int(old_id)) if old_id.isdigit() else None
            ok = True
            
            if not text or len(text) > 600:
                errors.append(f'سوال {i + 1}: متن سوال را کامل بنویسید.')
                ok = False
            if any(not o or len(o) > 300 for o in opts):
                errors.append(f'سوال {i + 1}: هر چهار گزینه را کامل بنویسید.')
                ok = False
            if correct_raw not in ('1', '2', '3', '4'):
                errors.append(f'سوال {i + 1}: گزینه صحیح را مشخص کنید.')
                ok = False
            try:
                score = float(score_raw)
                if not 0 <= score <= 100:
                    errors.append(f'سوال {i + 1}: نمره معتبر نیست.')
                    ok = False
            except (TypeError, ValueError):
                score = None
                errors.append(f'سوال {i + 1}: نمره معتبر نیست.')
                ok = False
            if image_file and image_file.filename:
                if not allowed_file(image_file.filename):
                    errors.append(f'سوال {i + 1}: فرمت تصویر مجاز نیست (PNG, JPG, WEBP, GIF).')
                    ok = False
                elif image_size(image_file) > MAX_IMAGE_SIZE:
                    errors.append(f'سوال {i + 1}: حجم تصویر نباید بیشتر از ۵ مگابایت باشد.')
                    ok = False
            
            redisplay.append({
                'id': old_id,
                'text': text,
                'image_path': old.image_path if old else None,
                'option1': opts[0], 'option2': opts[1],
                'option3': opts[2], 'option4': opts[3],
                'correct': int(correct_raw) if correct_raw in ('1', '2', '3', '4') else (old.correct if old else None),
                'score': score if score is not None else score_raw,
            })
            if ok:
                parsed.append((i, text, opts, int(correct_raw), score, old_id))
        if errors:
            for e in errors:
                flash(e, 'err')
            return render_template(
                'create_quiz.html',
                quiz=quiz,
                questions_data=redisplay,
                prefill={
                    'title': title,
                    'time_limit': request.form.get('time_limit', ''),
                    'shuffle': 'shuffle' in request.form,
                    'show_answers': 'show_answers' in request.form,
                }
            )
        quiz.title, quiz.time_limit = title, minutes
        quiz.shuffle_questions = 'shuffle' in request.form
        quiz.show_answers = 'show_answers' in request.form
        retained_paths = set()
        Question.query.filter_by(quiz_id=quiz.id).delete()
        db.session.flush()
        for i, text, opts, correct, score, old_id in parsed:
            old = old_questions.get(int(old_id)) if old_id.isdigit() else None
            image_path = old.image_path if old else None
            if request.form.get(f'q{i}_remove_image') == '1':
                image_path = None
            image_file = request.files.get(f'q{i}_image')
            if image_file and image_file.filename:
                image_path = save_question_image(image_file, quiz.token, i)
            if image_path:
                retained_paths.add(image_path)
            db.session.add(Question(quiz_id=quiz.id, text=text, image_path=image_path,
                                    option1=opts[0], option2=opts[1], option3=opts[2], option4=opts[3],
                                    correct=correct, score=score))
        for old in old_questions.values():
            if old.image_path and old.image_path not in retained_paths:
                path = os.path.join(UPLOAD_FOLDER, old.image_path)
                if os.path.exists(path):
                    os.remove(path)
        db.session.commit()
        flash('آزمون با موفقیت ویرایش شد.', 'ok')
        return redirect(url_for('quiz_detail', token=quiz.token))
    
    questions_data = [
        {
            'id': q.id,
            'text': q.text,
            'image_path': q.image_path,
            'option1': q.option1,
            'option2': q.option2,
            'option3': q.option3,
            'option4': q.option4,
            'correct': q.correct,
            'score': q.score
        }
        for q in quiz.questions
    ]
    
    return render_template('create_quiz.html', quiz=quiz, questions_data=questions_data, prefill={
        'title': quiz.title,
        'time_limit': quiz.time_limit,
        'shuffle': quiz.shuffle_questions,
        'show_answers': quiz.show_answers,
    })


@app.route('/teacher/quiz/<token>/duplicate', methods=['POST'])
def duplicate_quiz(token):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    
    original_quiz = func.owned_quiz_or_404(token)
    
    new_token = secrets.token_urlsafe(10)
    new_quiz = Quiz(
        teacher_id=session['teacher_id'],
        token=new_token,
        title=f"{original_quiz.title} (کپی)",
        time_limit=original_quiz.time_limit,
        shuffle_questions=original_quiz.shuffle_questions,
        show_answers=original_quiz.show_answers
    )
    db.session.add(new_quiz)
    db.session.flush()
    
    for idx, q in enumerate(original_quiz.questions):
        new_image_path = None
        if q.image_path:
            old_filepath = os.path.join(UPLOAD_FOLDER, q.image_path)
            ext = q.image_path.rsplit('.', 1)[1].lower()
            new_filename = f"{new_token}_q{idx}.{ext}"
            new_filepath = os.path.join(UPLOAD_FOLDER, new_filename)
            if os.path.exists(old_filepath):
                shutil.copy2(old_filepath, new_filepath)
                new_image_path = new_filename
        
        new_q = Question(
            quiz_id=new_quiz.id,
            text=q.text,
            image_path=new_image_path,
            option1=q.option1,
            option2=q.option2,
            option3=q.option3,
            option4=q.option4,
            correct=q.correct,
            score=q.score
        )
        db.session.add(new_q)
    
    db.session.commit()
    flash('آزمون با موفقیت کپی شد و اکنون قابل ویرایش است. ✅', 'ok')
    return redirect(url_for('edit_quiz', token=new_token))

@app.route('/teacher/quiz/<token>')
def quiz_detail(token):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    quiz = func.owned_quiz_or_404(token)
    done = [s for s in quiz.submissions if s.submitted_at]
    max_score = sum(q.score for q in quiz.questions)
    return render_template('quiz_detail.html', quiz=quiz, done_count=len(done), max_score=max_score)


@app.route('/teacher/quiz/<token>/delete', methods=['POST'])
def delete_quiz(token):
    quiz = func.owned_quiz_or_404(token)
    for q in quiz.questions:
        if q.image_path:
            filepath = os.path.join(UPLOAD_FOLDER, q.image_path)
            if os.path.exists(filepath):
                os.remove(filepath)
    db.session.delete(quiz)
    db.session.commit()
    flash('آزمون حذف شد.', 'ok')
    return redirect(url_for('panel'))


@app.route('/teacher/quiz/<token>/results')
def quiz_results(token):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    quiz = func.owned_quiz_or_404(token)
    subs = Submission.query.filter_by(quiz_id=quiz.id).filter(Submission.submitted_at.isnot(None)).order_by(Submission.submitted_at.desc()).all()
    avg = round(sum(s.score for s in subs) / len(subs), 1) if subs else 0
    best = max((s.score for s in subs), default=0)
    max_score = sum(q.score for q in quiz.questions)
    return render_template('quiz_results.html', quiz=quiz, subs=subs, avg=avg, best=best, max_score=max_score)

@app.route('/teacher/quiz/<token>/results/pdf')
def quiz_results_pdf(token):
    if not session.get('teacher_id'):
        return redirect(url_for('login'))
    
    quiz = func.owned_quiz_or_404(token)
    subs = Submission.query.filter_by(quiz_id=quiz.id).filter(Submission.submitted_at.isnot(None)).order_by(Submission.submitted_at.desc()).all()
    
    avg = round(sum(s.score for s in subs) / len(subs), 1) if subs else 0
    best = max((s.score for s in subs), default=0)
    max_score = sum(q.score for q in quiz.questions)

    font_path = os.path.join(app.root_path, 'static', 'fonts', 'IRANYakanX.woff')
    font_url = f"file://{os.path.abspath(font_path)}"
    
    html_content = render_template(
        'quiz_results_pdf.html', 
        quiz=quiz, 
        subs=subs, 
        avg=avg, 
        best=best,
        max_score=max_score,
        font_url=font_url
    )
    
    pdf_file = HTML(string=html_content, base_url=request.url_root).write_pdf()
    
    return Response(
        pdf_file,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=QuizDesk_{quiz.token}.pdf'}
    )

@app.route('/teacher/quiz/<token>/toggle-lock', methods=['POST'])
def toggle_quiz_lock(token):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    
    quiz = func.owned_quiz_or_404(token)
    quiz.is_locked = not quiz.is_locked
    db.session.commit()
    
    if quiz.is_locked:
        flash(f'آزمون «{quiz.title}» قفل شد. دانش‌آموزان نمی‌توانند در آن شرکت کنند.', 'ok')
    else:
        flash(f'آزمون «{quiz.title}» باز شد. دانش‌آموزان می‌توانند در آن شرکت کنند.', 'ok')
    
    return redirect(url_for('panel'))

@app.route('/teacher/submission/<int:sid>')
def submission_detail(sid):
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    sub = db.session.get(Submission, sid)
    if not sub or not sub.submitted_at:
        abort(404)
    quiz = db.session.get(Quiz, sub.quiz_id)
    if not quiz or quiz.teacher_id != session.get('teacher_id'):
        abort(403)
    qids = func.order_of(sub)
    qmap = {q.id: q for q in quiz.questions}
    questions = [qmap[qid] for qid in qids if qid in qmap]
    answers = {a.question_id: a for a in sub.answers}
    warns = WarningLog.query.filter_by(submission_id=sub.id).order_by(WarningLog.created_at.asc()).all()
    wrong = len([a for a in sub.answers if a.selected and not a.is_correct])
    blank = len([a for a in sub.answers if not a.selected])
    orig_index = {q.id: i + 1 for i, q in enumerate(quiz.questions)}
    return render_template('submission_detail.html', sub=sub, quiz=quiz, questions=questions, answers=answers, warns=warns, wrong=wrong, blank=blank, orig_index=orig_index)


@app.route('/take/<token>', methods=['GET', 'POST'])
def take_quiz(token):
    quiz = Quiz.query.filter_by(token=token).first_or_404()

    if quiz.is_locked:
        flash('این آزمون در حال حاضر قفل است و امکان شرکت در آن وجود ندارد.', 'err')
        return abort(403)

    key = f'take_{token}'
    sid = session.get(key)
    if sid:
        sub = db.session.get(Submission, sid)
        if sub and sub.quiz_id == quiz.id:
            if sub.submitted_at:
                return redirect(url_for('take_result', token=token))
            return redirect(url_for('take_exam', token=token))
    if request.method == 'POST':
        if not request.form.get('csrf_token'):
            abort(400)
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        class_no = request.form.get('class_no', '').strip()
        errors = []
        if not (1 <= len(first_name) <= 60): errors.append('نام الزامی است.')
        if not (1 <= len(last_name) <= 60): errors.append('نام خانوادگی الزامی است.')
        if not (1 <= len(class_no) <= 30): errors.append('شماره کلاس الزامی است.')
        if errors:
            for err in errors: flash(err, 'err')
        else:
            qids = [q.id for q in quiz.questions]
            if not qids:
                flash('این آزمون هنوز سوالی ندارد.', 'err')
                return redirect(url_for('take_quiz', token=token))
            if quiz.shuffle_questions:
                random.shuffle(qids)
            sub = Submission(quiz_id=quiz.id, first_name=first_name, last_name=last_name, class_no=class_no, question_order=json.dumps(qids), started_at=datetime.now())
            db.session.add(sub)
            db.session.commit()
            session[key] = sub.id
            return redirect(url_for('take_exam', token=token))
    return render_template('student_enter.html', quiz=quiz)


@app.route('/take/<token>/exam')
def take_exam(token):
    quiz, sub = func.get_take(token)
    if not quiz:
        abort(404)
    if not sub:
        flash('ابتدا اطلاعات خود را وارد کنید.', 'err')
        return redirect(url_for('take_quiz', token=token))
    if sub.submitted_at:
        return redirect(url_for('take_result', token=token))
    elapsed = (datetime.now() - sub.started_at).total_seconds()
    remaining = int(quiz.time_limit * 60 - elapsed)
    if remaining <= 0:
        func.finalize_submission(sub, None)
        flash('زمان آزمون به پایان رسید.', 'err')
        return redirect(url_for('take_result', token=token))
    qids = func.order_of(sub)
    qmap = {q.id: q for q in quiz.questions}
    questions = [qmap[qid] for qid in qids if qid in qmap]
    orig_index = {q.id: i + 1 for i, q in enumerate(quiz.questions)}
    return render_template('exam.html', quiz=quiz, sub=sub, questions=questions, remaining=remaining, orig_index=orig_index)


@app.route('/take/<token>/submit', methods=['POST'])
def take_submit(token):
    quiz, sub = func.get_take(token)
    if not quiz or not sub or sub.submitted_at:
        return redirect(url_for('take_quiz', token=token))
    # Lock the submission row so two simultaneous submits can't both pass the
    # submitted_at check and grade twice (which would create duplicate answers).
    locked = db.session.execute(
        db.select(Submission).where(Submission.id == sub.id).with_for_update()
    ).scalar_one_or_none()
    if locked is None or locked.submitted_at:
        db.session.rollback()
        return redirect(url_for('take_result', token=token))
    func.finalize_submission(locked, request.form)
    return redirect(url_for('take_result', token=token))


@app.route('/take/<token>/warn', methods=['POST'])
def take_warn(token):
    quiz, sub = func.get_take(token)
    if not quiz or not sub or sub.submitted_at:
        return {'ok': False}
    last = WarningLog.query.filter_by(submission_id=sub.id).order_by(WarningLog.created_at.desc()).first()
    if last and (datetime.now() - last.created_at).total_seconds() < 3:
        return {'ok': True, 'warnings': sub.warnings}
    db.session.add(WarningLog(submission_id=sub.id))
    sub.warnings = (sub.warnings or 0) + 1
    db.session.commit()
    return {'ok': True, 'warnings': sub.warnings}

@app.route('/take/<token>/result')
def take_result(token):
    quiz, sub = func.get_take(token)
    if not quiz or not sub or not sub.submitted_at:
        return redirect(url_for('take_quiz', token=token))
    
    answers = list(sub.answers)
    
    correct_count = sum(1 for a in answers if a.is_correct)
    wrong_count = sum(1 for a in answers if a.selected in (1, 2, 3, 4) and not a.is_correct)
    blank_count = sum(1 for a in answers if a.selected not in (1, 2, 3, 4))
    
    max_score = sum(float(q.score) for q in quiz.questions)
    percent = round((sub.score / max_score) * 100) if max_score > 0 else 0
    
    return render_template(
        'student_result.html', 
        quiz=quiz, 
        sub=sub, 
        percent=percent,
        max_score=max_score,
        correct_count=correct_count,
        wrong_count=wrong_count,
        blank_count=blank_count
    )

@app.route('/take/<token>/review')
def take_review(token):
    quiz, sub = func.get_take(token)
    if not quiz or not sub or not sub.submitted_at:
        return redirect(url_for('take_quiz', token=token))
    
    if not quiz.show_answers:
        flash('معلم نمایش پاسخ‌ها را غیرفعال کرده است.', 'err')
        return redirect(url_for('take_result', token=token))
    
    qids = func.order_of(sub)
    qmap = {q.id: q for q in quiz.questions}
    questions = [qmap[qid] for qid in qids if qid in qmap]
    answers = {a.question_id: a for a in sub.answers}
    questions_data = list(zip(questions, [answers.get(q.id) for q in questions]))
    orig_index = {q.id: i + 1 for i, q in enumerate(quiz.questions)}
    return render_template('student_review.html', quiz=quiz, sub=sub, questions_data=questions_data, orig_index=orig_index)

@app.route('/take/<token>/finish', methods=['POST'])
def take_finish(token):
    session.pop(f'take_{token}', None)
    return redirect(url_for('take_quiz', token=token))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/teacher/settings', methods=['GET', 'POST'])
def teacher_settings():
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    
    teacher = db.session.get(Teacher, session['teacher_id'])
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not func.verify_password(current_password, teacher.password_hash):
            flash('رمز عبور فعلی اشتباه است.', 'err')
        elif len(new_password) < 6:
            flash('رمز عبور جدید باید حداقل ۶ حرف باشد.', 'err')
        elif new_password != confirm_password:
            flash('تکرار رمز عبور جدید یکسان نیست.', 'err')
        else:
            teacher.password_hash = func.hash_password(new_password)
            db.session.commit()
            flash('رمز عبور شما با موفقیت تغییر کرد.', 'ok')
            return redirect(url_for('teacher_settings'))
    
    return render_template('settings.html', teacher=teacher)


@app.route('/teacher/delete_account', methods=['POST'])
def delete_account():
    if not session.get('teacher_id'):
        flash('لطفاً ابتدا وارد حساب خود شوید.', 'err')
        return redirect(url_for('login'))
    
    password = request.form.get('password', '')
    confirm_text = request.form.get('confirm_text', '')
    teacher = db.session.get(Teacher, session['teacher_id'])
    
    if not teacher:
        session.clear()
        return redirect(url_for('login'))
    
    if not func.verify_password(password, teacher.password_hash):
        flash('رمز عبور اشتباه است.', 'err')
        return redirect(url_for('teacher_settings'))
    
    if confirm_text.strip() != 'حذف حساب':
        flash('متن تایید نادرست است. باید دقیقاً بنویسید: حذف حساب', 'err')
        return redirect(url_for('teacher_settings'))
        
    for quiz in teacher.quizzes:
        for q in quiz.questions:
            if q.image_path:
                filepath = os.path.join(UPLOAD_FOLDER, q.image_path)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
    
    db.session.delete(teacher)
    db.session.commit()
    
    session.clear()
    flash('حساب شما و تمام اطلاعات مرتبط با آن با موفقیت حذف شد.', 'ok')
    return redirect(url_for('login'))


@app.errorhandler(404)
def err404(e):
    return render_template('message.html', icon='🔍', title='پیدا نشد', text='صفحه‌ای که دنبالش هستید وجود ندارد.', back_label='بازگشت', back_url=url_for('index')), 404

@app.errorhandler(403)
def err403(e):
    return render_template('message.html', icon='⛔', title='دسترسی غیرمجاز', text='شما اجازه دسترسی به این صفحه را ندارید.', back_label='بازگشت به پنل', back_url=url_for('panel')), 403

@app.errorhandler(CSRFError)
def err_csrf(e):
    return render_template('message.html', icon='🛡️', title='خطای امنیتی', text='توکن امنیتی نامعتبر است.', back_label='بازگشت', back_url=url_for('index')), 400

@app.errorhandler(500)
def err500(e):
    return render_template('message.html', icon='💥', title='خطای سرور', text='مشکلی پیش آمد. لطفاً دوباره تلاش کنید.', back_label='بازگشت به صفحه اصلی', back_url=url_for('index')), 500

@app.errorhandler(413)
def err413(e):
    return render_template('message.html', icon='🖼️', title='حجم فایل بیش از حد مجاز است', text='هر تصویر حداکثر ۵ مگابایت و حجم کل بارگذاری حداکثر ۱۰ مگابایت مجاز است.', back_label='بازگشت به صفحه اصلی', back_url=url_for('index')), 413


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
