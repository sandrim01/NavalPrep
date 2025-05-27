import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://postgres:wWLKGZYqmuobAQZyTPAZLmNrzJxcSKRd@tramway.proxy.rlwy.net:50771/railway")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Mail configuration
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER")
    
    # File upload configuration
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    
    # Mercado Pago configuration
    app.config["MERCADO_PAGO_ACCESS_TOKEN"] = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "TEST-access-token")
    app.config["MERCADO_PAGO_PUBLIC_KEY"] = os.environ.get("MERCADO_PAGO_PUBLIC_KEY", "TEST-public-key")
    
    # Security headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Login manager configuration
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor, faça login para acessar esta página."
    login_manager.login_message_category = "info"
    
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))
    
    # Create upload directory
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    # Register blueprints
    from routes import main_bp, auth_bp, admin_bp, professor_bp, payment_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(professor_bp, url_prefix="/professor")
    app.register_blueprint(payment_bp, url_prefix="/payment")
    
    # Create database tables
    with app.app_context():
        # Import models to ensure they're registered
        import models  # noqa: F401
        db.create_all()
        
        # Create default admin user if not exists
        from models import User, Role
        from werkzeug.security import generate_password_hash
        
        # Create roles if they don't exist
        admin_role = Role.query.filter_by(name="admin").first()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrador do sistema")
            db.session.add(admin_role)
        
        professor_role = Role.query.filter_by(name="professor").first()
        if not professor_role:
            professor_role = Role(name="professor", description="Professor")
            db.session.add(professor_role)
        
        student_role = Role.query.filter_by(name="student").first()
        if not student_role:
            student_role = Role(name="student", description="Aluno")
            db.session.add(student_role)
        
        db.session.commit()
        
        # Create default admin user
        admin_user = User.query.filter_by(email="admin@marinha.mil.br").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@marinha.mil.br",
                password_hash=generate_password_hash("admin123"),
                role_id=admin_role.id,
                is_active=True,
                is_verified=True,
                xp=0,
                level=1
            )
            db.session.add(admin_user)
            db.session.commit()
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
