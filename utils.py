import os
import json
import requests
from datetime import datetime, timezone
from flask import current_app
from flask_mail import Message
from app import mail
import mercadopago

def send_verification_email(email, username):
    """Send email verification"""
    try:
        msg = Message(
            subject='Verificação de conta - Academia Naval',
            recipients=[email],
            html=f"""
            <h2>Bem-vindo à Academia Naval, {username}!</h2>
            <p>Sua conta foi criada com sucesso.</p>
            <p>Para ativar sua conta e ter acesso completo aos cursos, realize o pagamento de um de nossos cursos.</p>
            <p>Permaneça forte e determinado em sua jornada!</p>
            <br>
            <p><strong>Academia Naval - Preparação para Fuzileiros</strong></p>
            """
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email sending error: {str(e)}")
        return False

def send_password_reset_email(email, token):
    """Send password reset email"""
    try:
        reset_url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/auth/reset-password/{token}"
        
        msg = Message(
            subject='Redefinir senha - Academia Naval',
            recipients=[email],
            html=f"""
            <h2>Redefinição de senha</h2>
            <p>Você solicitou a redefinição de sua senha.</p>
            <p><a href="{reset_url}">Clique aqui para redefinir sua senha</a></p>
            <p>Se você não solicitou esta redefinição, ignore este email.</p>
            <p>O link expira em 1 hora.</p>
            <br>
            <p><strong>Academia Naval</strong></p>
            """
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Password reset email error: {str(e)}")
        return False

def create_pix_payment(amount, description, user_email, user_name):
    """Create PIX payment using Mercado Pago"""
    try:
        # Initialize Mercado Pago SDK
        sdk = mercadopago.SDK(current_app.config['MERCADO_PAGO_ACCESS_TOKEN'])
        
        # Payment data
        payment_data = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "payer": {
                "email": user_email,
                "first_name": user_name.split()[0] if user_name else "Usuario",
                "last_name": " ".join(user_name.split()[1:]) if len(user_name.split()) > 1 else "Academia"
            },
            "notification_url": f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/payment/webhook"
        }
        
        # Create payment
        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]
        
        if payment_response["status"] == 201:
            return payment
        else:
            raise Exception(f"Payment creation failed: {payment}")
            
    except Exception as e:
        current_app.logger.error(f"PIX payment creation error: {str(e)}")
        raise e

def check_payment_status(payment_id):
    """Check payment status with Mercado Pago"""
    try:
        sdk = mercadopago.SDK(current_app.config['MERCADO_PAGO_ACCESS_TOKEN'])
        payment_response = sdk.payment().get(payment_id)
        
        if payment_response["status"] == 200:
            return payment_response["response"]
        else:
            return None
            
    except Exception as e:
        current_app.logger.error(f"Payment status check error: {str(e)}")
        return None

def allowed_file(filename, allowed_extensions):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    from werkzeug.utils import secure_filename
    return secure_filename(filename)

def calculate_user_rank(xp):
    """Calculate user rank based on XP"""
    ranks = [
        (0, "Recruta", "#8B4513"),
        (150, "Soldado", "#4682B4"),
        (300, "Cabo", "#32CD32"),
        (450, "3º Sargento", "#FFD700"),
        (600, "2º Sargento", "#FF8C00"),
        (750, "1º Sargento", "#DC143C"),
        (900, "Suboficial", "#8B0000"),
        (1050, "Aspirante", "#4B0082"),
        (1200, "Tenente", "#000080"),
        (1350, "Almirante", "#D4AF37")
    ]
    
    for i, (threshold, rank, color) in enumerate(reversed(ranks)):
        if xp >= threshold:
            return {
                'name': rank,
                'color': color,
                'level': len(ranks) - i,
                'threshold': threshold,
                'next_threshold': ranks[len(ranks) - i][0] if len(ranks) - i < len(ranks) else None
            }
    
    return ranks[0]

def get_achievement_progress(user, achievement_type):
    """Calculate achievement progress for user"""
    from models import QuizAttempt, Course
    
    progress = 0
    
    if achievement_type == 'quiz_master':
        # Count perfect quiz scores
        perfect_scores = QuizAttempt.query.filter_by(user_id=user.id).filter(QuizAttempt.score == 100).count()
        progress = min(perfect_scores / 10, 1.0)  # Need 10 perfect scores
        
    elif achievement_type == 'course_completion':
        # Count completed courses
        completed_courses = len([c for c in user.enrolled_courses if c.completed])
        progress = min(completed_courses / 5, 1.0)  # Need 5 completed courses
        
    elif achievement_type == 'forum_participation':
        # Count forum posts
        forum_posts = len(user.forum_posts)
        progress = min(forum_posts / 50, 1.0)  # Need 50 forum posts
        
    elif achievement_type == 'leaderboard_top':
        # Check if user is in top 10
        from app import db
        from models import User
        top_users = db.session.query(User.id).filter_by(is_active=True).order_by(User.xp.desc()).limit(10).all()
        user_ids = [u.id for u in top_users]
        progress = 1.0 if user.id in user_ids else 0.0
    
    return progress

def format_duration(minutes):
    """Format duration in minutes to human readable format"""
    if minutes < 60:
        return f"{minutes} min"
    else:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}min"

def format_file_size(bytes):
    """Format file size in bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"

def generate_quiz_statistics(quiz_attempts):
    """Generate statistics for quiz attempts"""
    if not quiz_attempts:
        return {
            'average_score': 0,
            'completion_rate': 0,
            'pass_rate': 0,
            'average_time': 0
        }
    
    total_attempts = len(quiz_attempts)
    completed_attempts = [a for a in quiz_attempts if a.completed_at]
    completed_count = len(completed_attempts)
    
    if completed_count == 0:
        return {
            'average_score': 0,
            'completion_rate': 0,
            'pass_rate': 0,
            'average_time': 0
        }
    
    # Calculate statistics
    average_score = sum(a.score for a in completed_attempts) / completed_count
    completion_rate = (completed_count / total_attempts) * 100
    
    # Assuming passing score is 70%
    passed_attempts = [a for a in completed_attempts if a.score >= 70]
    pass_rate = (len(passed_attempts) / completed_count) * 100
    
    # Average time
    times = [a.time_taken_minutes for a in completed_attempts if a.time_taken_minutes]
    average_time = sum(times) / len(times) if times else 0
    
    return {
        'average_score': round(average_score, 1),
        'completion_rate': round(completion_rate, 1),
        'pass_rate': round(pass_rate, 1),
        'average_time': round(average_time, 1)
    }

def get_course_progress(user, course):
    """Calculate user progress in a specific course"""
    total_lessons = len(course.lessons)
    total_quizzes = len(course.quizzes)
    
    if total_lessons == 0 and total_quizzes == 0:
        return 0
    
    # Count completed lessons (simplified - in real app, track lesson completion)
    completed_lessons = total_lessons  # Assuming all lessons are "completed" when viewed
    
    # Count passed quizzes
    passed_quizzes = 0
    for quiz in course.quizzes:
        best_attempt = QuizAttempt.query.filter_by(user_id=user.id, quiz_id=quiz.id)\
                                       .filter(QuizAttempt.score >= quiz.passing_score)\
                                       .order_by(QuizAttempt.score.desc()).first()
        if best_attempt:
            passed_quizzes += 1
    
    # Calculate overall progress
    total_items = total_lessons + total_quizzes
    completed_items = completed_lessons + passed_quizzes
    
    return (completed_items / total_items) * 100 if total_items > 0 else 0

def create_sample_data():
    """Create sample data for development (only if no data exists)"""
    from models import Role, User, Course, Lesson, Quiz, Question, QuestionOption, ForumCategory, Achievement
    from app import db
    
    # Only create sample data if there are no courses
    if Course.query.count() > 0:
        return
    
    # Create forum categories
    categories = [
        ForumCategory(name="Dúvidas Técnicas", description="Tire suas dúvidas sobre o conteúdo dos cursos", order=1),
        ForumCategory(name="Estratégias de Prova", description="Compartilhe dicas e estratégias para as provas", order=2),
        ForumCategory(name="Material Complementar", description="Compartilhe materiais e recursos extras", order=3),
        ForumCategory(name="Experiências", description="Compartilhe suas experiências nos concursos", order=4)
    ]
    
    for category in categories:
        db.session.add(category)
    
    # Create sample courses
    courses = [
        Course(
            title="Matemática para Cabo da Marinha",
            description="Curso completo de matemática para o concurso de Cabo da Marinha, abordando todos os tópicos do edital.",
            price=97.90,
            duration_hours=40,
            level="intermediate",
            category="matematica"
        ),
        Course(
            title="Português Militar - Cabo e Sargento",
            description="Português focado em concursos militares com gramática, interpretação de texto e redação.",
            price=87.90,
            duration_hours=35,
            level="intermediate",
            category="portugues"
        ),
        Course(
            title="História Naval Brasileira",
            description="História da Marinha do Brasil e principais batalhas navais para concursos militares.",
            price=67.90,
            duration_hours=25,
            level="beginner",
            category="historia"
        ),
        Course(
            title="Legislação Militar Completa",
            description="Regulamentos, estatutos e legislação militar para Cabo e Sargento da Marinha.",
            price=77.90,
            duration_hours=30,
            level="advanced",
            category="legislacao"
        )
    ]
    
    for course in courses:
        db.session.add(course)
    
    # Create achievements
    achievements = [
        Achievement(
            name="Primeiro Login",
            description="Realizou o primeiro login na plataforma",
            icon="🎯",
            xp_reward=10,
            requirement_type="login",
            requirement_value="1"
        ),
        Achievement(
            name="Nota Máxima",
            description="Obteve 100% em um quiz",
            icon="🏆",
            xp_reward=25,
            requirement_type="quiz_score",
            requirement_value="100"
        ),
        Achievement(
            name="Mestre dos Quizzes",
            description="Passou em 10 quizzes diferentes",
            icon="🎖️",
            xp_reward=50,
            requirement_type="quiz_completion",
            requirement_value="10"
        ),
        Achievement(
            name="Participante Ativo",
            description="Fez 50 postagens no fórum",
            icon="💬",
            xp_reward=30,
            requirement_type="forum_posts",
            requirement_value="50"
        ),
        Achievement(
            name="Top 10 Ranking",
            description="Chegou ao top 10 do ranking geral",
            icon="🥇",
            badge_color="#D4AF37",
            xp_reward=100,
            requirement_type="leaderboard",
            requirement_value="10"
        )
    ]
    
    for achievement in achievements:
        db.session.add(achievement)
    
    db.session.commit()
    current_app.logger.info("Sample data created successfully")

def backup_database():
    """Create database backup (simplified version)"""
    try:
        # In a real application, you would use pg_dump or similar
        backup_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'users_count': User.query.count(),
            'courses_count': Course.query.count(),
            'payments_count': Payment.query.count()
        }
        
        # Save to file or cloud storage
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = os.path.join(current_app.instance_path, 'backups', backup_filename)
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        current_app.logger.info(f"Database backup created: {backup_filename}")
        return backup_filename
        
    except Exception as e:
        current_app.logger.error(f"Database backup error: {str(e)}")
        return None
