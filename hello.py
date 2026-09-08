import os
from flask import Flask, render_template, session, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard to guess string'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bootstrap = Bootstrap(app)
moment = Moment(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return '<Role %r>' % self.name


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def __repr__(self):
        return '<User %r>' % self.username


class NameForm(FlaskForm):
    name = StringField(
        'What is your name?',
        filters=[lambda value: value.strip() if value else value],
        validators=[DataRequired(), Length(max=64)]
    )
    submit = SubmitField('Submit')


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Role=Role)


@app.cli.command('init-db')
def init_db():
    """Cria as tabelas e associa os cadastros sem função a User."""
    db.create_all()

    user_role = Role.query.filter_by(name='User').first()

    if user_role is None:
        user_role = Role(name='User')
        db.session.add(user_role)

    for user in User.query.filter_by(role_id=None).all():
        user.role = user_role

    db.session.commit()
    print('Banco pronto. Cadastros existentes preservados.')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()

        if user is None:
            user_role = Role.query.filter_by(name='User').first()

            if user_role is None:
                user_role = Role(name='User')
                db.session.add(user_role)

            user = User(
                username=form.name.data,
                role=user_role
            )

            db.session.add(user)
            db.session.commit()

            session['known'] = False
        else:
            session['known'] = True

        session['name'] = form.name.data
        return redirect(url_for('index'))

    users = User.query.order_by(User.id).all()

    return render_template(
        'index.html',
        form=form,
        name=session.get('name'),
        known=session.get('known', False),
        users=users
    )


if __name__ == '__main__':
    app.run()