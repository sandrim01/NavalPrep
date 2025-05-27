import os
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db, limiter
from models import *
from forms import *
from utils import send_verification_email, create_pix_payment, check_payment_status
import bleach

# Create blueprints
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)
admin_bp = Blueprint('admin', __name__)
professor_bp = Blueprint('professor', __name__)
payment_bp = Blueprint('payment', __name__)

# Main routes
@main_bp.route('/')
def index():
    """Homepage with course overview and leaderboard"""
    courses = Course.query.filter_by(is_active=True).limit(6).all()
    
    # Get top 10 users by XP for leaderboard
    top_users = User.query.filter_by(is_active=True).order_by(User.xp.desc()).limit(10).all()
    
    return render_template('index.html', courses=courses, top_users=top_users)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with progress and achievements"""
    if not current_user.is_active:
        flash('Sua conta precisa ser ativada com pagamento para acessar o conteúdo completo.', 'warning')
        return redirect(url_for('main.courses'))
    
    # Get user's enrolled courses
    enrolled_courses = current_user.enrolled_courses
    
    # Get recent quiz attempts
    recent_attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
                                     .order_by(QuizAttempt.completed_at.desc())\
                                     .limit(5).all()
    
    # Get user achievements
    achievements = current_user.achievements
    
    # Calculate progress statistics
    total_courses = len(enrolled_courses)
    completed_courses = sum(1 for course in enrolled_courses if any(
        enrollment.completed for enrollment in course_enrollments 
        if enrollment.c.user_id == current_user.id and enrollment.c.course_id == course.id
    ))
    
    return render_template('dashboard.html', 
                         enrolled_courses=enrolled_courses,
                         recent_attempts=recent_attempts,
                         achievements=achievements,
                         total_courses=total_courses,
                         completed_courses=completed_courses)

@main_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('profile.html')

@main_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.rank = form.rank.data
        current_user.registration_number = form.registration_number.data
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('main.profile'))

@main_bp.route('/courses')
def courses():
    """Course listing page"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    
    query = Course.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    
    courses = query.paginate(page=page, per_page=12, error_out=False)
    categories = db.session.query(Course.category).distinct().all()
    
    return render_template('courses.html', courses=courses, categories=categories, selected_category=category)

@main_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    """Course detail page"""
    course = Course.query.get_or_404(course_id)
    
    # Check if user is enrolled
    is_enrolled = False
    if current_user.is_authenticated:
        is_enrolled = course in current_user.enrolled_courses
    
    return render_template('course_detail.html', course=course, is_enrolled=is_enrolled)

@main_bp.route('/quiz/<int:quiz_id>')
@login_required
def quiz(quiz_id):
    """Quiz taking page"""
    if not current_user.is_active:
        flash('Você precisa de uma conta ativa para fazer quizzes.', 'warning')
        return redirect(url_for('main.courses'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if user is enrolled in the course
    if quiz.course not in current_user.enrolled_courses:
        flash('Você precisa estar matriculado no curso para fazer este quiz.', 'warning')
        return redirect(url_for('main.course_detail', course_id=quiz.course_id))
    
    return render_template('quiz.html', quiz=quiz)

@main_bp.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def submit_quiz(quiz_id):
    """Submit quiz answers"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Create quiz attempt
    attempt = QuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz.id,
        started_at=datetime.now(timezone.utc)
    )
    db.session.add(attempt)
    db.session.flush()
    
    correct_answers = 0
    total_questions = len(quiz.questions)
    
    # Process answers
    for question in quiz.questions:
        answer_id = request.form.get(f'question_{question.id}')
        if answer_id:
            selected_option = QuestionOption.query.get(answer_id)
            is_correct = selected_option.is_correct if selected_option else False
            
            # Save answer
            answer = QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option_id=answer_id,
                is_correct=is_correct
            )
            db.session.add(answer)
            
            if is_correct:
                correct_answers += 1
    
    # Calculate score
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    attempt.score = score
    attempt.completed_at = datetime.now(timezone.utc)
    
    # Award XP based on performance
    if score >= quiz.passing_score:
        xp_reward = 20 + int(score / 10)  # Base 20 XP + bonus
        current_user.add_xp(xp_reward)
        flash(f'Parabéns! Você passou no quiz com {score:.1f}% e ganhou {xp_reward} XP!', 'success')
    else:
        flash(f'Você precisa de pelo menos {quiz.passing_score}% para passar. Sua nota: {score:.1f}%', 'warning')
    
    db.session.commit()
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/forum')
def forum():
    """Forum main page"""
    categories = ForumCategory.query.filter_by(is_active=True).order_by(ForumCategory.order).all()
    return render_template('forum.html', categories=categories)

@main_bp.route('/forum/category/<int:category_id>')
def forum_category(category_id):
    """Forum category page with topics"""
    category = ForumCategory.query.get_or_404(category_id)
    page = request.args.get('page', 1, type=int)
    
    topics = ForumTopic.query.filter_by(category_id=category_id)\
                           .order_by(ForumTopic.is_pinned.desc(), ForumTopic.updated_at.desc())\
                           .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('forum_category.html', category=category, topics=topics)

@main_bp.route('/forum/topic/<int:topic_id>')
def topic_detail(topic_id):
    """Forum topic detail with posts"""
    topic = ForumTopic.query.get_or_404(topic_id)
    page = request.args.get('page', 1, type=int)
    
    posts = ForumPost.query.filter_by(topic_id=topic_id)\
                          .order_by(ForumPost.created_at.asc())\
                          .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('topic_detail.html', topic=topic, posts=posts)

@main_bp.route('/forum/topic/<int:topic_id>/reply', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def reply_topic(topic_id):
    """Reply to forum topic"""
    topic = ForumTopic.query.get_or_404(topic_id)
    
    if topic.is_locked:
        flash('Este tópico está bloqueado para novas respostas.', 'warning')
        return redirect(url_for('main.topic_detail', topic_id=topic_id))
    
    form = ForumReplyForm()
    if form.validate_on_submit():
        # Sanitize content
        clean_content = bleach.clean(form.content.data, 
                                   tags=['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li'],
                                   strip=True)
        
        post = ForumPost(
            content=clean_content,
            topic_id=topic.id,
            author_id=current_user.id
        )
        db.session.add(post)
        
        # Update topic timestamp
        topic.updated_at = datetime.now(timezone.utc)
        
        # Award XP for forum participation
        current_user.add_xp(5)
        
        db.session.commit()
        flash('Resposta adicionada com sucesso! Você ganhou 5 XP.', 'success')
    
    return redirect(url_for('main.topic_detail', topic_id=topic_id))

# Authentication routes
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Get student role
        student_role = Role.query.filter_by(name='student').first()
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            full_name=form.full_name.data,
            rank=form.rank.data,
            registration_number=form.registration_number.data,
            role_id=student_role.id,
            xp=0,
            level=1
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Send verification email
        try:
            send_verification_email(user.email, user.username)
            flash('Conta criada com sucesso! Verifique seu email para ativar a conta.', 'success')
        except Exception as e:
            flash('Conta criada, mas não foi possível enviar email de verificação.', 'warning')
        
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('main.index'))

# Payment routes
@payment_bp.route('/course/<int:course_id>')
@login_required
def payment_page(course_id):
    """Payment page for course"""
    course = Course.query.get_or_404(course_id)
    
    # Check if user is already enrolled
    if course in current_user.enrolled_courses:
        flash('Você já está matriculado neste curso.', 'info')
        return redirect(url_for('main.course_detail', course_id=course_id))
    
    return render_template('payment.html', course=course)

@payment_bp.route('/create-pix/<int:course_id>', methods=['POST'])
@login_required
@limiter.limit("3 per minute")
def create_pix(course_id):
    """Create PIX payment"""
    course = Course.query.get_or_404(course_id)
    
    try:
        payment_data = create_pix_payment(
            amount=course.price,
            description=f"Curso: {course.title}",
            user_email=current_user.email,
            user_name=current_user.full_name or current_user.username
        )
        
        # Save payment record
        payment = Payment(
            external_id=payment_data['id'],
            amount=course.price,
            status='pending',
            payment_method='pix',
            pix_qr_code=payment_data.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code'),
            pix_qr_code_base64=payment_data.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code_base64'),
            user_id=current_user.id,
            course_id=course.id
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'qr_code': payment.pix_qr_code,
            'qr_code_base64': payment.pix_qr_code_base64
        })
        
    except Exception as e:
        current_app.logger.error(f"PIX payment creation error: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao criar pagamento PIX'}), 500

@payment_bp.route('/webhook', methods=['POST'])
@limiter.exempt  # Webhook should not be rate limited
def payment_webhook():
    """Mercado Pago webhook for payment updates"""
    try:
        data = request.get_json()
        
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            
            if payment_id:
                # Check payment status
                payment_info = check_payment_status(payment_id)
                
                if payment_info and payment_info.get('status') == 'approved':
                    # Find our payment record
                    payment = Payment.query.filter_by(external_id=payment_id).first()
                    
                    if payment:
                        payment.status = 'approved'
                        payment.updated_at = datetime.now(timezone.utc)
                        
                        # Activate user account
                        payment.user.is_active = True
                        
                        # Enroll user in course
                        if payment.course not in payment.user.enrolled_courses:
                            payment.user.enrolled_courses.append(payment.course)
                        
                        # Award XP for course enrollment
                        payment.user.add_xp(50)
                        
                        db.session.commit()
                        
                        current_app.logger.info(f"Payment {payment_id} approved for user {payment.user.email}")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Internal error'}), 500

# Admin routes
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard"""
    if current_user.role.name != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    # Get statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_courses = Course.query.count()
    total_payments = Payment.query.filter_by(status='approved').count()
    
    # Recent activities
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         total_courses=total_courses,
                         total_payments=total_payments,
                         recent_users=recent_users,
                         recent_payments=recent_payments)

# Course management routes
@admin_bp.route('/manage-courses')
@login_required
def manage_courses():
    """Admin course management"""
    if current_user.role.name not in ['admin', 'professor']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin/courses.html', courses=courses)

@admin_bp.route('/courses/new', methods=['GET', 'POST'])
@login_required
def create_course():
    """Create new course"""
    if current_user.role.name not in ['admin', 'professor']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    form = CourseForm()
    if form.validate_on_submit():
        course = Course(
            title=form.title.data,
            description=form.description.data,
            price=form.price.data,
            duration_hours=form.duration_hours.data,
            level=form.level.data,
            category=form.category.data
        )
        
        db.session.add(course)
        db.session.commit()
        
        flash('Curso criado com sucesso!', 'success')
        return redirect(url_for('admin.course_detail', course_id=course.id))
    
    return render_template('admin/course_form.html', form=form, title='Novo Curso')

@admin_bp.route('/courses/<int:course_id>')
@login_required
def course_detail(course_id):
    """Course detail with modules/missions"""
    if current_user.role.name not in ['admin', 'professor']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    course = Course.query.get_or_404(course_id)
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order).all()
    quizzes = Quiz.query.filter_by(course_id=course_id).order_by(Quiz.id).all()
    
    return render_template('admin/course_detail.html', course=course, lessons=lessons, quizzes=quizzes)

@admin_bp.route('/courses/<int:course_id>/lessons/new', methods=['GET', 'POST'])
@login_required
def create_lesson(course_id):
    """Create new lesson/mission"""
    if current_user.role.name not in ['admin', 'professor']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    course = Course.query.get_or_404(course_id)
    form = LessonForm()
    
    if form.validate_on_submit():
        # Get next order number
        last_lesson = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order.desc()).first()
        next_order = (last_lesson.order + 1) if last_lesson else 1
        
        lesson = Lesson(
            title=form.title.data,
            content=form.content.data,
            video_url=form.video_url.data,
            duration_minutes=form.duration_minutes.data,
            order=form.order.data or next_order,
            course_id=course_id
        )
        
        db.session.add(lesson)
        db.session.commit()
        
        flash('Missão criada com sucesso!', 'success')
        return redirect(url_for('admin.course_detail', course_id=course_id))
    
    return render_template('admin/lesson_form.html', form=form, course=course, title='Nova Missão')

@admin_bp.route('/users')
@login_required
def users():
    """Manage users"""
    if current_user.role.name != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc())\
                     .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/courses')
@login_required
def courses():
    """Manage courses"""
    if current_user.role.name != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    courses = Course.query.order_by(Course.created_at.desc())\
                         .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/courses.html', courses=courses)

# Professor routes
@professor_bp.route('/dashboard')
@login_required
def dashboard():
    """Professor dashboard"""
    if current_user.role.name not in ['professor', 'admin']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('professor/dashboard.html')

@professor_bp.route('/materials')
@login_required
def materials():
    """Manage course materials"""
    if current_user.role.name not in ['professor', 'admin']:
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.index'))
    
    courses = Course.query.filter_by(is_active=True).all()
    return render_template('professor/materials.html', courses=courses)

# API endpoints for real-time updates
@main_bp.route('/api/leaderboard')
def api_leaderboard():
    """API endpoint for leaderboard data"""
    top_users = User.query.filter_by(is_active=True)\
                         .order_by(User.xp.desc())\
                         .limit(10).all()
    
    data = []
    for i, user in enumerate(top_users, 1):
        data.append({
            'rank': i,
            'username': user.username,
            'military_level': user.get_military_level(),
            'xp': user.xp,
            'level': user.level
        })
    
    return jsonify(data)

@main_bp.route('/api/user-progress')
@login_required
def api_user_progress():
    """API endpoint for user progress data"""
    progress_data = {
        'xp': current_user.xp,
        'level': current_user.level,
        'military_level': current_user.get_military_level(),
        'progress_to_next': current_user.get_progress_to_next_level(),
        'achievements_count': len(current_user.achievements)
    }
    
    return jsonify(progress_data)

# File upload handler
@main_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
