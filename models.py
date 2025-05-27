from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db
import uuid

# Association table for user achievements
user_achievements = db.Table('user_achievements',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('achievement_id', db.Integer, db.ForeignKey('achievement.id'), primary_key=True),
    db.Column('earned_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)

# Association table for course enrollments
course_enrollments = db.Table('course_enrollments',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True),
    db.Column('enrolled_at', db.DateTime, default=lambda: datetime.now(timezone.utc)),
    db.Column('progress', db.Float, default=0.0),
    db.Column('completed', db.Boolean, default=False)
)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    
    # Relationships
    users = db.relationship('User', backref='role', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Profile information
    full_name = db.Column(db.String(100))
    rank = db.Column(db.String(50))  # Military rank
    registration_number = db.Column(db.String(20))  # Military registration
    
    # Account status
    is_active = db.Column(db.Boolean, default=False)  # Activated after payment
    is_verified = db.Column(db.Boolean, default=False)  # Email verified
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    # Gamification
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    
    # Role
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    
    # Relationships
    forum_posts = db.relationship('ForumPost', backref='author', lazy=True)
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)
    achievements = db.relationship('Achievement', secondary=user_achievements, backref='users')
    enrolled_courses = db.relationship('Course', secondary=course_enrollments, backref='enrolled_users')
    
    def get_military_level(self):
        """Return military level based on XP"""
        levels = [
            (0, "Recruta"),
            (150, "Soldado"),
            (300, "Cabo"),
            (450, "3º Sargento"),
            (600, "2º Sargento"),
            (750, "1º Sargento"),
            (900, "Suboficial"),
            (1050, "Aspirante"),
            (1200, "Tenente"),
            (1350, "Almirante")
        ]
        
        for xp_threshold, rank in reversed(levels):
            if self.xp >= xp_threshold:
                return rank
        return "Recruta"
    
    def add_xp(self, points):
        """Add XP and update level"""
        self.xp += points
        new_level = (self.xp // 150) + 1
        if new_level > self.level:
            self.level = new_level
        db.session.commit()
    
    def get_progress_to_next_level(self):
        """Get progress percentage to next level"""
        current_level_xp = (self.level - 1) * 150
        next_level_xp = self.level * 150
        progress_xp = self.xp - current_level_xp
        return (progress_xp / 150) * 100

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    duration_hours = db.Column(db.Integer)
    level = db.Column(db.String(20))  # Beginner, Intermediate, Advanced
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    lessons = db.relationship('Lesson', backref='course', lazy=True, cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='course', lazy=True, cascade='all, delete-orphan')

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    video_url = db.Column(db.String(200))  # YouTube embed URL
    pdf_file = db.Column(db.String(200))  # PDF file path
    order = db.Column(db.Integer, default=0)
    duration_minutes = db.Column(db.Integer)
    
    # Foreign keys
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    time_limit_minutes = db.Column(db.Integer, default=60)
    passing_score = db.Column(db.Integer, default=70)  # Percentage
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Relationships
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='multiple_choice')  # multiple_choice, true_false
    points = db.Column(db.Integer, default=1)
    order = db.Column(db.Integer, default=0)
    
    # Foreign keys
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    
    # Relationships
    options = db.relationship('QuestionOption', backref='question', lazy=True, cascade='all, delete-orphan')

class QuestionOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    
    # Foreign keys
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    score = db.Column(db.Float)  # Percentage score
    time_taken_minutes = db.Column(db.Integer)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    
    # Relationships
    answers = db.relationship('QuizAnswer', backref='attempt', lazy=True, cascade='all, delete-orphan')

class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_option.id'))
    is_correct = db.Column(db.Boolean)
    
    # Foreign keys
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))  # Icon class or emoji
    badge_color = db.Column(db.String(7), default='#D4AF37')  # Golden color
    xp_reward = db.Column(db.Integer, default=0)
    requirement_type = db.Column(db.String(50))  # quiz_score, course_completion, etc.
    requirement_value = db.Column(db.String(100))  # JSON string with requirements

class ForumCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    topics = db.relationship('ForumTopic', backref='category', lazy=True)

class ForumTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('forum_category.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    posts = db.relationship('ForumPost', backref='topic', lazy=True, cascade='all, delete-orphan')
    author = db.relationship('User', backref='forum_topics')

class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_official = db.Column(db.Boolean, default=False)  # Marked as official by professor
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True)  # Mercado Pago payment ID
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    payment_method = db.Column(db.String(20), default='pix')
    
    # PIX specific
    pix_qr_code = db.Column(db.Text)
    pix_qr_code_base64 = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Relationships
    course = db.relationship('Course', backref='payments')

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
