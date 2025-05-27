from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, PasswordField, BooleanField, SelectField, IntegerField, FloatField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange
from models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar de mim')

class RegistrationForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[
        DataRequired(), 
        Length(min=4, max=20, message='Nome de usuário deve ter entre 4 e 20 caracteres')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Nome completo', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Nome deve ter entre 2 e 100 caracteres')
    ])
    rank = SelectField('Patente atual', choices=[
        ('civil', 'Civil'),
        ('soldado', 'Soldado'),
        ('cabo', 'Cabo'),
        ('3_sargento', '3º Sargento'),
        ('2_sargento', '2º Sargento'),
        ('1_sargento', '1º Sargento'),
        ('suboficial', 'Suboficial'),
        ('aspirante', 'Aspirante'),
        ('tenente', 'Tenente'),
        ('capitao', 'Capitão'),
        ('major', 'Major'),
        ('tenente_coronel', 'Tenente Coronel'),
        ('coronel', 'Coronel')
    ], validators=[DataRequired()])
    registration_number = StringField('Número de matrícula militar', validators=[
        Length(max=20, message='Número de matrícula muito longo')
    ])
    password = PasswordField('Senha', validators=[
        DataRequired(),
        Length(min=8, message='Senha deve ter pelo menos 8 caracteres')
    ])
    password2 = PasswordField('Confirmar senha', validators=[
        DataRequired(),
        EqualTo('password', message='Senhas devem ser iguais')
    ])
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Nome de usuário já existe. Escolha outro.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email já cadastrado. Use outro email.')

class ProfileForm(FlaskForm):
    full_name = StringField('Nome completo', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    rank = SelectField('Patente atual', choices=[
        ('civil', 'Civil'),
        ('soldado', 'Soldado'),
        ('cabo', 'Cabo'),
        ('3_sargento', '3º Sargento'),
        ('2_sargento', '2º Sargento'),
        ('1_sargento', '1º Sargento'),
        ('suboficial', 'Suboficial'),
        ('aspirante', 'Aspirante'),
        ('tenente', 'Tenente'),
        ('capitao', 'Capitão'),
        ('major', 'Major'),
        ('tenente_coronel', 'Tenente Coronel'),
        ('coronel', 'Coronel')
    ], validators=[DataRequired()])
    registration_number = StringField('Número de matrícula militar', validators=[
        Length(max=20)
    ])

class CourseForm(FlaskForm):
    title = StringField('Título do curso', validators=[
        DataRequired(),
        Length(min=5, max=100)
    ])
    description = TextAreaField('Descrição', validators=[
        DataRequired(),
        Length(min=20, max=1000)
    ])
    price = FloatField('Preço (R$)', validators=[
        DataRequired(),
        NumberRange(min=0, message='Preço deve ser positivo')
    ])
    duration_hours = IntegerField('Duração (horas)', validators=[
        DataRequired(),
        NumberRange(min=1, max=1000)
    ])
    level = SelectField('Nível', choices=[
        ('beginner', 'Iniciante'),
        ('intermediate', 'Intermediário'),
        ('advanced', 'Avançado')
    ], validators=[DataRequired()])
    category = SelectField('Categoria', choices=[
        ('matematica', 'Matemática'),
        ('portugues', 'Português'),
        ('historia', 'História'),
        ('geografia', 'Geografia'),
        ('ciencias', 'Ciências'),
        ('conhecimentos_gerais', 'Conhecimentos Gerais'),
        ('legislacao', 'Legislação Militar'),
        ('tatica', 'Tática e Estratégia')
    ], validators=[DataRequired()])

class LessonForm(FlaskForm):
    title = StringField('Título da aula', validators=[
        DataRequired(),
        Length(min=5, max=100)
    ])
    content = TextAreaField('Conteúdo', validators=[
        Length(max=5000)
    ])
    video_url = StringField('URL do vídeo (YouTube)', validators=[
        Length(max=200)
    ])
    pdf_file = FileField('Arquivo PDF', validators=[
        FileAllowed(['pdf'], 'Apenas arquivos PDF são permitidos')
    ])
    duration_minutes = IntegerField('Duração (minutos)', validators=[
        NumberRange(min=1, max=300)
    ])
    order = IntegerField('Ordem', validators=[
        NumberRange(min=0)
    ])

class QuizForm(FlaskForm):
    title = StringField('Título do quiz', validators=[
        DataRequired(),
        Length(min=5, max=100)
    ])
    description = TextAreaField('Descrição', validators=[
        Length(max=500)
    ])
    time_limit_minutes = IntegerField('Tempo limite (minutos)', validators=[
        DataRequired(),
        NumberRange(min=5, max=180)
    ])
    passing_score = IntegerField('Nota mínima (%)', validators=[
        DataRequired(),
        NumberRange(min=0, max=100)
    ])

class QuestionForm(FlaskForm):
    text = TextAreaField('Pergunta', validators=[
        DataRequired(),
        Length(min=10, max=1000)
    ])
    question_type = SelectField('Tipo', choices=[
        ('multiple_choice', 'Múltipla escolha'),
        ('true_false', 'Verdadeiro/Falso')
    ], validators=[DataRequired()])
    points = IntegerField('Pontos', validators=[
        DataRequired(),
        NumberRange(min=1, max=10)
    ])
    order = IntegerField('Ordem', validators=[
        NumberRange(min=0)
    ])

class QuestionOptionForm(FlaskForm):
    text = StringField('Opção', validators=[
        DataRequired(),
        Length(min=1, max=500)
    ])
    is_correct = BooleanField('Resposta correta')
    order = IntegerField('Ordem', validators=[
        NumberRange(min=0)
    ])

class ForumTopicForm(FlaskForm):
    title = StringField('Título do tópico', validators=[
        DataRequired(),
        Length(min=5, max=200)
    ])
    content = TextAreaField('Conteúdo', validators=[
        DataRequired(),
        Length(min=20, max=5000)
    ])
    category_id = SelectField('Categoria', coerce=int, validators=[DataRequired()])

class ForumReplyForm(FlaskForm):
    content = TextAreaField('Resposta', validators=[
        DataRequired(),
        Length(min=10, max=5000)
    ])

class SearchForm(FlaskForm):
    query = StringField('Buscar', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])

class PasswordResetRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])

class PasswordResetForm(FlaskForm):
    password = PasswordField('Nova senha', validators=[
        DataRequired(),
        Length(min=8)
    ])
    password2 = PasswordField('Confirmar nova senha', validators=[
        DataRequired(),
        EqualTo('password')
    ])

class PaymentForm(FlaskForm):
    course_id = HiddenField('Course ID', validators=[DataRequired()])
    payment_method = SelectField('Método de pagamento', choices=[
        ('pix', 'PIX'),
        ('credit_card', 'Cartão de crédito'),
        ('debit_card', 'Cartão de débito')
    ], default='pix', validators=[DataRequired()])

class AdminUserForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[
        DataRequired(),
        Length(min=4, max=20)
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Nome completo', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    role_id = SelectField('Função', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Conta ativa')
    is_verified = BooleanField('Email verificado')

class BulkActionForm(FlaskForm):
    action = SelectField('Ação', choices=[
        ('activate', 'Ativar'),
        ('deactivate', 'Desativar'),
        ('delete', 'Excluir')
    ], validators=[DataRequired()])
    selected_items = HiddenField('Itens selecionados')
