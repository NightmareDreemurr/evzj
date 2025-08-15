from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

from app.models import db, User
from .forms import LoginForm, RegistrationForm
from . import auth_bp


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            username=form.username.data,
            phone=form.phone.data or None,
            role=form.role.data,
            password_hash=generate_password_hash(form.password.data),
            full_name=form.username.data
        )
        db.session.add(user)
        db.session.commit()
        flash('恭喜，您已成功注册！现在可以登录了。', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        account = form.account.data
        password = form.password.data
        
        user = User.query.filter(or_(User.email == account, User.username == account, User.phone == account)).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('登录成功！', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
                
            return redirect(url_for('main.index'))
        else:
            flash('账号或密码无效，请重试。', 'error')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出。', 'info')
    return redirect(url_for('auth.login')) 