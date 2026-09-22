import os
import requests

from flask import Flask, render_template, session, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv


# ---------------------------------------------------------
# CONFIGURAÇÕES INICIAIS
# ---------------------------------------------------------

basedir = os.path.abspath(os.path.dirname(__file__))

# Carrega as variáveis do arquivo .env
load_dotenv(os.path.join(basedir, '.env'))


FUNCOES = (
    'Administrator',
    'Moderator',
    'User'
)


app = Flask(__name__)


# ---------------------------------------------------------
# CONFIGURAÇÕES DO FLASK
# ---------------------------------------------------------

app.config['SECRET_KEY'] = 'hard to guess string'

app.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# ---------------------------------------------------------
# CONFIGURAÇÕES DO MAILGUN
# ---------------------------------------------------------

app.config['API_KEY'] = os.environ.get('API_KEY')
app.config['API_URL'] = os.environ.get('API_URL')
app.config['API_FROM'] = os.environ.get('API_FROM')

app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')

app.config['ALUNO_NOME'] = os.environ.get('ALUNO_NOME')
app.config['ALUNO_PRONTUARIO'] = os.environ.get('ALUNO_PRONTUARIO')


# ---------------------------------------------------------
# EXTENSÕES
# ---------------------------------------------------------

bootstrap = Bootstrap(app)
moment = Moment(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)


# ---------------------------------------------------------
# MODELOS
# ---------------------------------------------------------

class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(64),
        unique=True
    )

    users = db.relationship(
        'User',
        backref='role',
        lazy='dynamic'
    )

    def __repr__(self):
        return '<Role %r>' % self.name


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(64),
        unique=True,
        index=True
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey('roles.id')
    )

    def __repr__(self):
        return '<User %r>' % self.username


# ---------------------------------------------------------
# FORMULÁRIO
# ---------------------------------------------------------

class NameForm(FlaskForm):

    name = StringField(
        'What is your name?',
        filters=[
            lambda value: value.strip()
            if value else value
        ],
        validators=[
            DataRequired(),
            Length(max=64)
        ]
    )

    role = SelectField(
        'Role?',
        choices=[
            ('Administrator', 'Administrator'),
            ('Moderator', 'Moderator'),
            ('User', 'User')
        ],
        validators=[
            DataRequired()
        ]
    )

    submit = SubmitField(
        'Submit'
    )


# ---------------------------------------------------------
# MAILGUN
# ---------------------------------------------------------

def enviar_email_novo_usuario(usuario):

    api_url = app.config['API_URL']
    api_key = app.config['API_KEY']
    remetente = app.config['API_FROM']

    email_aluno = app.config['FLASKY_ADMIN']
    nome_aluno = app.config['ALUNO_NOME']
    prontuario = app.config['ALUNO_PRONTUARIO']

    if not api_url:
        raise RuntimeError(
            'API_URL não configurada.'
        )

    if not api_key:
        raise RuntimeError(
            'API_KEY não configurada.'
        )

    if not remetente:
        raise RuntimeError(
            'API_FROM não configurado.'
        )

    if not email_aluno:
        raise RuntimeError(
            'FLASKY_ADMIN não configurado.'
        )

    corpo = f"""
Novo usuário cadastrado na aplicação Flask.

Aluno responsável:
Nome: {nome_aluno}
Prontuário: {prontuario}

Usuário cadastrado:
Nome: {usuario.username}
Função: {usuario.role.name}
"""

    dados = [
        (
            'from',
            remetente
        ),
        (
            'to',
            'flaskaulasweb@zohomail.com'
        ),
        (
            'to',
            email_aluno
        ),
        (
            'subject',
            f"{app.config['FLASKY_MAIL_SUBJECT_PREFIX']} Novo usuário cadastrado"
        ),
        (
            'text',
            corpo
        )
    ]

    resposta = requests.post(
        api_url,
        auth=(
            'api',
            api_key
        ),
        data=dados,
        timeout=15
    )

    print(
        'Mailgun Status:',
        resposta.status_code
    )

    print(
        'Mailgun Resposta:',
        resposta.text
    )

    resposta.raise_for_status()

    return resposta


# ---------------------------------------------------------
# BANCO DE DADOS
# ---------------------------------------------------------

def preparar_banco():

    db.create_all()

    for nome_funcao in FUNCOES:

        funcao = Role.query.filter_by(
            name=nome_funcao
        ).first()

        if funcao is None:

            db.session.add(
                Role(
                    name=nome_funcao
                )
            )

    db.session.flush()

    funcao_user = Role.query.filter_by(
        name='User'
    ).first()

    usuarios_sem_funcao = User.query.filter_by(
        role_id=None
    ).all()

    for usuario in usuarios_sem_funcao:

        usuario.role = funcao_user

    db.session.commit()


with app.app_context():
    preparar_banco()


# ---------------------------------------------------------
# SHELL
# ---------------------------------------------------------

@app.shell_context_processor
def make_shell_context():

    return {
        'db': db,
        'User': User,
        'Role': Role
    }


# ---------------------------------------------------------
# COMANDO PARA INICIALIZAR BANCO
# ---------------------------------------------------------

@app.cli.command('init-db')
def init_db():

    preparar_banco()

    print(
        'Banco pronto. Cadastros existentes preservados.'
    )


# ---------------------------------------------------------
# ERROS
# ---------------------------------------------------------

@app.errorhandler(404)
def page_not_found(e):

    return render_template(
        '404.html'
    ), 404


@app.errorhandler(500)
def internal_server_error(e):

    return render_template(
        '500.html'
    ), 500


# ---------------------------------------------------------
# PÁGINA PRINCIPAL
# ---------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():

    form = NameForm()

    if form.validate_on_submit():

        user = User.query.filter_by(
            username=form.name.data
        ).first()

        role = Role.query.filter_by(
            name=form.role.data
        ).first()

        # -------------------------------------------------
        # NOVO USUÁRIO
        # -------------------------------------------------

        if user is None:

            user = User(
                username=form.name.data,
                role=role
            )

            db.session.add(user)

            # Salva temporariamente para termos acesso
            # ao usuário antes do commit
            db.session.flush()

            try:

                enviar_email_novo_usuario(
                    user
                )

            except Exception as erro:

                db.session.rollback()

                print(
                    'Erro ao enviar e-mail:',
                    erro
                )

                raise

            db.session.commit()

            session['known'] = False

        # -------------------------------------------------
        # USUÁRIO JÁ EXISTENTE
        # -------------------------------------------------

        else:

            user.role = role

            db.session.commit()

            session['known'] = True


        session['name'] = form.name.data

        return redirect(
            url_for('index')
        )


    # -----------------------------------------------------
    # LISTAGEM DOS USUÁRIOS
    # -----------------------------------------------------

    users = User.query.order_by(
        User.id
    ).all()

    roles = []

    for nome_funcao in FUNCOES:

        role = Role.query.filter_by(
            name=nome_funcao
        ).first()

        roles.append({
            'name': role.name,
            'users': role.users.order_by(
                User.id
            ).all()
        })


    quantidade_usuarios = User.query.count()
    quantidade_funcoes = Role.query.count()


    return render_template(
        'index.html',
        form=form,
        name=session.get('name'),
        known=session.get(
            'known',
            False
        ),
        users=users,
        roles=roles,
        quantidade_usuarios=quantidade_usuarios,
        quantidade_funcoes=quantidade_funcoes
    )


# ---------------------------------------------------------
# EXECUÇÃO
# ---------------------------------------------------------

if __name__ == '__main__':

    app.run()