"""认证路由 - 登录、注册、登出"""
import os
import re
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify

from services.user_service import user_service
from utils.redis_client import persist_session_token, drop_session_token
from utils.decorators import login_required


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")
_PASSWORD_RE = re.compile(r"^\S{1,128}$")
# allow slash in job/company/school names (e.g. "教师 / 教育工作者")
_SCHOOL_MAJOR_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9 _./-]{2,50}$")
_PHONE_RE = re.compile(r"^1\d{10}$")


def _validate_login_input(user_id: str, password: str) -> str | None:
    if not user_id:
        return "请输入手机号"
    if not _PHONE_RE.match(user_id):
        return "手机号格式不正确，请输入 11 位手机号"
    if not password:
        return "请输入密码"
    if not _PASSWORD_RE.match(password):
        return "密码格式不正确，请不要包含空白字符，最长 128 字符"
    return None


def _validate_registration_input(school: str, major: str, password: str, confirm_password: str, job: str, company: str, user_id: str | None) -> str | None:
    # if job indicates student, require school and major; otherwise they are optional
    is_student = bool(job and '学生' in job)
    if is_student:
        if not school:
            return "请输入学校名称"
        if not _SCHOOL_MAJOR_RE.match(school):
            return "学校名称格式不正确，建议 2-50 字符且不包含特殊符号"
        if not major:
            return "请输入专业"
        if not _SCHOOL_MAJOR_RE.match(major):
            return "专业格式不正确，建议 2-50 字符且不包含特殊符号"
    if not job:
        return "请输入职业/职务"
    if not _SCHOOL_MAJOR_RE.match(job):
        return "职业格式不正确，建议 2-50 字符且不包含特殊符号"
    # company can be optional (学生可为空)
    if company and not _SCHOOL_MAJOR_RE.match(company):
        return "公司名称格式不正确，建议 2-50 字符且不包含特殊符号"
    if not password:
        return "请输入密码"
    if not _PASSWORD_RE.match(password):
        return "密码格式不正确，请不要包含空白字符，最长 128 字符"
    if password != confirm_password:
        return "两次输入的密码不一致"

    if user_id:
        if not _PHONE_RE.match(user_id):
            return "手机号格式不正确，请输入 11 位手机号"
    else:
        # user_id (手机号) is required
        return "请输入手机号"
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """登录页面和处理"""
    if request.method == "GET":
        return render_template("login.html")
    
    # POST：验证手机号和密码（手机号作为 user_id）
    user_id = request.form.get('user_id', '').strip()
    password = request.form.get('password', '')

    error = _validate_login_input(user_id, password)
    if error:
        return render_template("login.html", error=error), 400
    
    user = user_service.authenticate(user_id, password)
    if not user:
        return render_template("login.html", error="手机号或密码错误")
    
    # 登录成功
    token = uuid.uuid4().hex
    session['user_id'] = user.user_id
    session['login_token'] = token
    persist_session_token(user.user_id, token)
    return redirect(url_for('index'))


@auth_bp.route("/registration", methods=["GET", "POST"])
def registration():
    """注册页面和处理"""
    if request.method == "GET":
        return render_template("registration.html")
    
    if request.method == "POST":
        school = request.form.get('school', '').strip()
        major = request.form.get('major', '').strip()
        job = request.form.get('job', '').strip()
        company = request.form.get('company', '').strip()
        user_id = request.form.get('user_id', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        error = _validate_registration_input(school, major, password, confirm_password, job, company, user_id)
        if error:
            return render_template("registration.html", error=error), 400
        
        # 读取学生证二进制数据（可选），超过 16MB 拒绝
        student_card_binary = None
        if 'student_card' in request.files:
            file = request.files['student_card']
            if file and getattr(file, "filename", ""):
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > int(1.5 * 1024 * 1024):
                    return render_template(
                        "registration.html",
                        error="学生证照片不能超过 1.5MB，请压缩后再上传"
                    ), 400
                student_card_binary = file.read()
        
        # 填充默认值：非学生时可留空，数据库要求 school/major 非空，填入默认占位
        is_student = bool(job and '学生' in job)
        final_school = school if (is_student and school) else (school or '无')
        final_major = major if (is_student and major) else (major or '无')
        final_company = company or ''

        # 注册用户（使用手机号作为 user_id）
        success, message = user_service.register(
            user_id, password, final_school, final_major, job, final_company, student_card_binary
        )
        
        # 如果是 AJAX 请求，返回 JSON 便于前端弹窗处理
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if success:
                return jsonify({"success": True, "message": message}), 200
            else:
                return jsonify({"success": False, "message": message}), 400

        if success:
            return redirect(url_for('auth.login'))
        else:
            return render_template("registration.html", error=message), 400
    
    return jsonify({"status": "error", "content": "Invalid request method."}), 405

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """登出"""
    user_id = session.pop('user_id', None)
    session.pop('login_token', None)
    if user_id:
        drop_session_token(user_id)
    return redirect(url_for('index'))


@auth_bp.route("/current-user", methods=["GET"])
@login_required
def get_current_user():
    """获取当前用户信息"""
    current_user_id = session.get('user_id')
    _, profession = user_service.get_user_and_profession(current_user_id)
    return jsonify({
        "status": "success",
        "user_id": current_user_id,
        "profession": profession or "未知"
    })


@auth_bp.route("/registration2", methods=["GET"])
def registration2():
    """快速注册页面（单页表单版本，两个分支由前端控制）"""
    return render_template("registration2.html")
