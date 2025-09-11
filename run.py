import os
import uuid
import datetime
import qrcode
import json
from PIL import Image, ImageDraw, ImageFont
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

# 1. Khởi tạo ứng dụng và cấu hình
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Tắt cache template

# Cấu hình thư mục để lưu ảnh tải lên
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'Uploads', 'event_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Các định dạng file ảnh cho phép
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Danh sách câu hỏi bảo mật
SECURITY_QUESTIONS = [
    "Tên trường tiểu học đầu tiên của bạn là gì?",
    "Tên thú cưng đầu tiên của bạn là gì?",
    "Biệt danh thời thơ ấu của bạn là gì?",
    "Tên người bạn thân nhất của bạn ở trường trung học là gì?",
    "Tên món ăn yêu thích của bạn là gì?"
]

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Hàm kiểm tra định dạng file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 2. Định nghĩa các Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'doan_truong', 'sinh_vien'
    student_id = db.Column(db.String(20), unique=True, nullable=True)
    cccd = db.Column(db.String(20), unique=True, nullable=True)
    fullname = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    faculty = db.Column(db.String(100), nullable=True)
    student_class = db.Column(db.String(50), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    course = db.Column(db.String(50), nullable=True)
    security_question = db.Column(db.String(200), nullable=True)
    security_answer_hash = db.Column(db.String(128), nullable=True)
    tickets = db.relationship('Ticket', back_populates='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_security_answer(self, answer):
        self.security_answer_hash = generate_password_hash(answer.lower().strip())

    def check_security_answer(self, answer):
        return check_password_hash(self.security_answer_hash, answer.lower().strip())

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    total_tickets = db.Column(db.Integer, nullable=False)
    available_tickets = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(200), nullable=True)
    tickets = db.relationship('Ticket', back_populates='event', lazy=True)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    ticket_code = db.Column(db.String(50), unique=True, nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False)
    is_used = db.Column(db.Boolean, default=False)
    user_info_json = db.Column(db.String(1000), nullable=True)
    event_info_json = db.Column(db.String(1000), nullable=True)
    user = db.relationship('User', back_populates='tickets', lazy=True)
    event = db.relationship('Event', back_populates='tickets', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 3. Logic duyệt và tạo vé điện tử
class TicketController:
    @staticmethod
    def process_booking(user_id, event_id):
        event = Event.query.get(event_id)
        user = User.query.get(user_id)
        if not event or event.available_tickets <= 0 or not user:
            return None

        event.available_tickets -= 1
        db.session.commit()

        ticket_code = str(uuid.uuid4())
        user_info_json = json.dumps({
            "fullname": user.fullname,
            "student_id": user.student_id,
            "student_class": user.student_class,
            "faculty": user.faculty,
            "email": user.email,
        })
        event_info_json = json.dumps({
            "name": event.name,
            "date": event.date.strftime('%d/%m/%Y'),
            "location": event.location,
        })

        new_ticket = Ticket(
            user_id=user_id,
            event_id=event_id,
            ticket_code=ticket_code,
            is_approved=True,
            is_used=False,
            user_info_json=user_info_json,
            event_info_json=event_info_json
        )
        db.session.add(new_ticket)
        db.session.commit()

        qr_data = {
            "ticket_code": ticket_code,
            "user_id": user_id,
            "event_id": event_id
        }
        
        TicketController.generate_e_ticket(json.dumps(qr_data), new_ticket)
        return ticket_code

    @staticmethod
    def generate_e_ticket(qr_data_json, ticket):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data_json)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        
        qr_size = 200
        qr_img = qr_img.resize((qr_size, qr_size))

        template_path = os.path.join(app.root_path, 'static', 'ticket_template.png')
        try:
            template = Image.open(template_path).resize((800, 400))
        except FileNotFoundError:
            template = Image.new('RGB', (800, 400), color='white')

        draw = ImageDraw.Draw(template)
        font_path = "arial.ttf"
        try:
            font = ImageFont.truetype(font_path, 20)
        except IOError:
            font = ImageFont.load_default()

        user_info = json.loads(ticket.user_info_json)
        event_info = json.loads(ticket.event_info_json)

        draw.text((50, 50), f"Sự kiện: {event_info['name']}", fill="black", font=font)
        draw.text((50, 80), f"Ngày: {event_info['date']}", fill="black", font=font)
        draw.text((50, 110), f"Người đặt: {user_info['fullname']}", fill="black", font=font)
        draw.text((50, 140), f"Mã vé: {ticket.ticket_code}", fill="black", font=font)

        left = 500
        top = 100
        right = left + qr_size
        bottom = top + qr_size

        template.paste(qr_img, (left, top, right, bottom))
        
        tickets_dir = os.path.join(app.root_path, 'static', 'images', 'tickets')
        os.makedirs(tickets_dir, exist_ok=True)
        ticket_path = os.path.join(tickets_dir, f"{ticket.ticket_code}.png")
        template.save(ticket_path)

# 4. Các Routes và quyền truy cập
def required_roles(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('Bạn không có quyền truy cập trang này.', 'danger')
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        user = User.query.filter(or_(
            User.username == identifier,
            User.email == identifier
        )).first()
        if user and user.security_question and user.security_answer_hash:
            return redirect(url_for('verify_security_answer', user_id=user.id))
        else:
            flash('Tên đăng nhập hoặc email không tồn tại, hoặc tài khoản chưa thiết lập câu hỏi bảo mật.', 'danger')
            return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/verify-security-answer/<int:user_id>', methods=['GET', 'POST'])
def verify_security_answer(user_id):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    if not user.security_question or not user.security_answer_hash:
        flash('Tài khoản này chưa thiết lập câu hỏi bảo mật.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        answer = request.form.get('security_answer')
        if user.check_security_answer(answer):
            return redirect(url_for('reset_password', user_id=user.id))
        else:
            flash('Câu trả lời bảo mật không đúng.', 'danger')
            return redirect(url_for('verify_security_answer', user_id=user_id))
    
    return render_template('verify_security_answer.html', user_id=user_id, security_question=user.security_question)

@app.route('/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash('Mật khẩu và xác nhận mật khẩu không khớp.', 'danger')
            return redirect(url_for('reset_password', user_id=user_id))
        
        if not (len(password) >= 8 and any(c.isupper() for c in password) and any(c.isdigit() for c in password) and any(c in '!@#$%^&*()_+-=[]{}|;:,.<>/?' for c in password)):
            flash('Mật khẩu phải dài ít nhất 8 ký tự, chứa chữ hoa, số và ký tự đặc biệt.', 'danger')
            return redirect(url_for('reset_password', user_id=user_id))
        
        user.set_password(password)
        db.session.commit()
        flash('Mật khẩu đã được đặt lại thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', user_id=user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'sinh_vien':
            return redirect(url_for('student_dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'doan_truong':
            return redirect(url_for('doan_truong_dashboard'))
            
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter(or_(
            User.username == username,
            User.email == username,
            User.student_id == username,
            User.cccd == username
        )).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            
            if user.role == 'sinh_vien':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'doan_truong':
                return redirect(url_for('doan_truong_dashboard'))
        
        flash('Sai tên đăng nhập hoặc mật khẩu.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        dob_str = request.form.get('dob')
        student_class = request.form.get('student_class')
        faculty = request.form.get('faculty')
        course = request.form.get('course')
        cccd = request.form.get('cccd')
        student_id = request.form.get('student_id')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        security_question = request.form.get('security_question')
        security_answer = request.form.get('security_answer')

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'danger')
            return redirect(url_for('register'))
        
        if not (any(c.isupper() for c in password) and any(c in '!@#$%^&*()_+-=[]{}|;:,.<>/?' for c in password)):
            flash('Mật khẩu phải chứa ít nhất một chữ cái viết hoa và một ký tự đặc biệt.', 'danger')
            return redirect(url_for('register'))

        if not security_question or not security_answer:
            flash('Vui lòng chọn câu hỏi bảo mật và cung cấp câu trả lời.', 'danger')
            return redirect(url_for('register'))

        username_to_use = cccd if cccd and len(cccd) == 12 and cccd.isdigit() else student_id
        
        if not username_to_use:
            flash('Vui lòng nhập số CCCD hoặc Mã sinh viên hợp lệ để đăng ký.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username_to_use).first():
            flash(f'{username_to_use} đã được sử dụng làm tên đăng nhập.', 'danger')
            return redirect(url_for('register'))
        
        if student_id and User.query.filter_by(student_id=student_id).first():
            flash('Mã sinh viên đã được đăng ký.', 'danger')
            return redirect(url_for('register'))
        if cccd and User.query.filter_by(cccd=cccd).first():
            flash('Số CCCD đã được đăng ký.', 'danger')
            return redirect(url_for('register'))
        if email and User.query.filter_by(email=email).first():
            flash('Email đã được đăng ký.', 'danger')
            return redirect(url_for('register'))
        
        try:
            dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

            new_user = User(
                username=username_to_use,
                role='sinh_vien',
                fullname=fullname,
                dob=dob,
                student_class=student_class,
                faculty=faculty,
                course=course,
                cccd=cccd,
                student_id=student_id,
                email=email,
                phone=phone,
                security_question=security_question
            )
            
            new_user.set_password(password)
            new_user.set_security_answer(security_answer)
            db.session.add(new_user)
            db.session.commit()
            
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
        except ValueError:
            flash('Ngày sinh không hợp lệ.', 'danger')
            return redirect(url_for('register'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi đăng ký. Vui lòng kiểm tra lại thông tin. Lỗi: {e}', 'danger')
            return redirect(url_for('register'))
            
    return render_template('register.html', security_questions=SECURITY_QUESTIONS)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'doan_truong':
        return redirect(url_for('doan_truong_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/student/dashboard')
@login_required
@required_roles('sinh_vien')
def student_dashboard():
    events = Event.query.all()
    return render_template('student.html', events=events)

@app.route('/student/my-profile', methods=['GET', 'POST'])
@login_required
@required_roles('sinh_vien')
def my_profile():
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        fullname = request.form.get('fullname')
        student_id = request.form.get('student_id')
        cccd = request.form.get('cccd')
        email = request.form.get('email')
        phone = request.form.get('phone')
        faculty = request.form.get('faculty')
        student_class = request.form.get('student_class')
        password = request.form.get('password')
        dob_str = request.form.get('dob')
        course = request.form.get('course')

        # Kiểm tra dữ liệu bắt buộc
        if not fullname or not email:
            flash('Họ và tên và email là bắt buộc.', "error")
            return render_template('student_profile.html', user=current_user)

        # Kiểm tra xem student_id hoặc cccd đã tồn tại chưa (trừ chính user hiện tại)
        existing_user_by_student_id = User.query.filter_by(student_id=student_id).first() if student_id else None
        existing_user_by_cccd = User.query.filter_by(cccd=cccd).first() if cccd else None
        if existing_user_by_student_id and existing_user_by_student_id.id != current_user.id:
            flash('Mã sinh viên đã được sử dụng bởi người dùng khác.', "error")
            return render_template('student_profile.html', user=current_user)
        if existing_user_by_cccd and existing_user_by_cccd.id != current_user.id:
            flash('Số CCCD đã được sử dụng bởi người dùng khác.', "error")
            return render_template('student_profile.html', user=current_user)
        if User.query.filter_by(email=email).first() and User.query.filter_by(email=email).first().id != current_user.id:
            flash('Email đã được sử dụng bởi người dùng khác.', "error")
            return render_template('student_profile.html', user=current_user)

        # Cập nhật thông tin người dùng
        current_user.fullname = fullname
        current_user.student_id = student_id
        current_user.cccd = cccd
        current_user.email = email
        current_user.phone = phone
        current_user.faculty = faculty
        current_user.student_class = student_class

        # Xử lý ngày sinh
        if dob_str:
            try:
                current_user.dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Định dạng ngày sinh không hợp lệ. Vui lòng dùng YYYY-MM-DD.', "error")
                return render_template('student_profile.html', user=current_user)

        current_user.course = course

        # Cập nhật mật khẩu nếu có
        if password:
            if not (len(password) >= 8 and any(c.isupper() for c in password) and any(c.isdigit() for c in password) and any(c in '!@#$%^&*()_+-=[]{}|;:,.<>/?' for c in password)):
                flash('Mật khẩu phải dài ít nhất 8 ký tự, chứa chữ hoa, số và ký tự đặc biệt.', "error")
                return render_template('student_profile.html', user=current_user)
            current_user.set_password(password)

        try:
            db.session.commit()
            flash('Hồ sơ đã được cập nhật thành công!', 'success')
            return redirect(url_for('my_profile'))
        except IntegrityError:
            db.session.rollback()
            flash('Lỗi khi cập nhật hồ sơ. Vui lòng kiểm tra thông tin (có thể do trùng lặp).', 'error')
            return render_template('student_profile.html', user=current_user)
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi máy chủ: {str(e)}', 'error')
            return render_template('student_profile.html', user=current_user)

    return render_template('student_profile.html', user=current_user)

@app.route('/student/my-tickets')
@login_required
@required_roles('sinh_vien')
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/student/search', methods=['GET'])
@login_required
@required_roles('sinh_vien')
def search_events():
    query = request.args.get('query', '')
    events = Event.query.filter(Event.name.ilike(f'%{query}%')).all()
    return render_template('student.html', events=events)

@app.route('/student/book/<int:event_id>')
@login_required
@required_roles('sinh_vien')
def book_ticket(event_id):
    event = Event.query.get_or_404(event_id)
    existing_ticket = Ticket.query.filter_by(user_id=current_user.id, event_id=event_id).first()
    if existing_ticket:
        flash('Bạn đã có vé cho sự kiện này rồi.', 'info')
        return redirect(url_for('view_ticket', ticket_code=existing_ticket.ticket_code))
        
    return redirect(url_for('confirm_booking', event_id=event_id))

@app.route('/student/confirm-booking/<int:event_id>', methods=['GET', 'POST'])
@login_required
@required_roles('sinh_vien')
def confirm_booking(event_id):
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        existing_ticket = Ticket.query.filter_by(user_id=current_user.id, event_id=event_id).first()
        if existing_ticket:
            flash('Bạn đã có vé cho sự kiện này rồi.', 'info')
            return redirect(url_for('view_ticket', ticket_code=existing_ticket.ticket_code))
        
        ticket_code = TicketController.process_booking(current_user.id, event_id)
        if ticket_code:
            flash('Đặt vé thành công!', 'success')
            return redirect(url_for('view_ticket', ticket_code=ticket_code))
        else:
            flash('Vé đã hết hoặc có lỗi xảy ra.', 'danger')
            return redirect(url_for('student_dashboard'))
    
    return render_template('confirm_booking.html', event=event)

@app.route('/student/ticket/<ticket_code>')
@login_required
@required_roles('sinh_vien')
def view_ticket(ticket_code):
    ticket = Ticket.query.filter_by(ticket_code=ticket_code, user_id=current_user.id).first()
    if not ticket:
        flash('Không tìm thấy vé.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    event = Event.query.get_or_404(ticket.event_id)
    return render_template('ticket_success.html', ticket=ticket, event=event)

@app.route('/download/ticket/<ticket_code>')
@login_required
@required_roles('sinh_vien')
def download_ticket(ticket_code):
    ticket = Ticket.query.filter_by(ticket_code=ticket_code, user_id=current_user.id).first()
    if not ticket:
        flash('Không tìm thấy vé để tải xuống.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    ticket_filename = f"{ticket_code}.png"
    ticket_path = os.path.join(app.root_path, 'static', 'images', 'tickets')
    
    try:
        return send_from_directory(
            directory=ticket_path,
            path=ticket_filename,
            as_attachment=True,
            mimetype='image/png'
        )
    except FileNotFoundError:
        flash('File vé không tồn tại trên máy chủ.', 'danger')
        return redirect(url_for('view_ticket', ticket_code=ticket_code))

@app.route('/admin/dashboard')
@login_required
@required_roles('admin')
def admin_dashboard():
    total_users = User.query.count()
    total_tickets = Ticket.query.count()
    total_events = Event.query.count()
    event_stats = db.session.query(
        Event.name,
        Event.total_tickets,
        Event.available_tickets
    ).all()
    faculty_stats = db.session.query(
        User.faculty,
        db.func.count(User.id)
    ).group_by(User.faculty).all()
    faculty_ticket_stats = db.session.query(
        User.faculty,
        db.func.count(Ticket.id)
    ).join(User).group_by(User.faculty).all()
    return render_template(
        'admin.html',
        total_users=total_users,
        total_tickets=total_tickets,
        total_events=total_events,
        event_stats=event_stats,
        faculty_stats=faculty_stats,
        faculty_ticket_stats=faculty_ticket_stats
    )

@app.route('/doantruong/dashboard')
@login_required
@required_roles('doan_truong')
def doan_truong_dashboard():
    events = Event.query.all()
    return render_template('doantruong.html', events=events)

@app.route('/admin/add-event', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def add_event():
    if request.method == 'POST':
        name = request.form.get('name')
        date_str = request.form.get('date')
        location = request.form.get('location')
        description = request.form.get('description')
        total_tickets = request.form.get('total_tickets')
        
        image_url = None
        if 'event_image' in request.files:
            file = request.files['event_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                image_url = url_for('uploaded_file', filename=unique_filename, _external=True)
            elif file.filename != '':
                flash('File ảnh không hợp lệ!', 'danger')
                return redirect(url_for('add_event'))
        
        try:
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            total_tickets = int(total_tickets)
            
            new_event = Event(
                name=name,
                date=date,
                location=location,
                description=description,
                total_tickets=total_tickets,
                available_tickets=total_tickets,
                image_url=image_url
            )
            db.session.add(new_event)
            db.session.commit()
            flash('Sự kiện đã được thêm thành công!', 'success')
            
            if current_user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif current_user.role == 'doan_truong':
                return redirect(url_for('doan_truong_dashboard'))

        except (ValueError, TypeError) as e:
            flash(f'Lỗi khi thêm sự kiện: Vui lòng kiểm tra định dạng dữ liệu. Lỗi: {e}', 'danger')
            return redirect(url_for('add_event'))

    return render_template('add_event.html')

@app.route('/admin/edit-event/<int:event_id>', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            old_tickets = event.total_tickets
            new_total_tickets = int(request.form.get('total_tickets'))
            
            event.name = request.form.get('name')
            event.date = datetime.datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            event.location = request.form.get('location')
            event.description = request.form.get('description')
            event.total_tickets = new_total_tickets
            
            tickets_sold = old_tickets - event.available_tickets
            event.available_tickets = new_total_tickets - tickets_sold

            if 'event_image' in request.files:
                file = request.files['event_image']
                if file and allowed_file(file.filename):
                    if event.image_url:
                        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(event.image_url))
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = str(uuid.uuid4()) + "_" + filename
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    event.image_url = url_for('uploaded_file', filename=unique_filename, _external=True)
                elif file.filename != '':
                    flash('File ảnh không hợp lệ!', 'danger')
                    return redirect(url_for('edit_event', event_id=event.id))
            
            db.session.commit()
            flash('Sự kiện đã được cập nhật thành công!', 'success')
            
            if current_user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif current_user.role == 'doan_truong':
                return redirect(url_for('doan_truong_dashboard'))
        
        except Exception as e:
            flash(f'Lỗi khi cập nhật sự kiện: {e}', 'danger')

    return render_template('edit_event.html', event=event)

@app.route('/admin/delete-event/<int:event_id>', methods=['POST'])
@login_required
@required_roles('admin', 'doan_truong')
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    try:
        tickets_to_delete = Ticket.query.filter_by(event_id=event_id).all()
        for ticket in tickets_to_delete:
            ticket_path = os.path.join(app.root_path, 'static', 'images', 'tickets', f"{ticket.ticket_code}.png")
            if os.path.exists(ticket_path):
                os.remove(ticket_path)
            db.session.delete(ticket)

        if event.image_url:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(event.image_url))
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(event)
        db.session.commit()
        flash('Sự kiện và các vé liên quan đã được xóa thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa sự kiện: {e}', 'danger')
        
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'doan_truong':
        return redirect(url_for('doan_truong_dashboard'))
    
@app.route('/admin/manage-events')
@login_required
@required_roles('admin', 'doan_truong')
def manage_events():
    events = Event.query.order_by(Event.date.asc()).all()
    return render_template('manage_events.html', events=events)    

@app.route('/static/uploads/event_images/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/qr-scan')
@login_required
@required_roles('admin', 'doan_truong')
def qr_scan():
    return render_template('qr_scan.html')

@app.route('/qr-result', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def qr_result():
    user_info = None
    ticket_status = "Không có dữ liệu để xử lý."

    if request.method == 'POST':
        qr_data_string = None
        
        if request.is_json:
            try:
                data = request.get_json()
                qr_data_string = data.get('qr_data')
            except Exception as e:
                flash("Lỗi xử lý dữ liệu JSON. Vui lòng thử lại.", 'error')
                return render_template('qr_result.html', user_info=None, ticket_status="Lỗi xử lý dữ liệu")
        else:
            qr_data_string = request.form.get('qr_data')

        if not qr_data_string:
            flash("Không có dữ liệu QR để xử lý.", 'error')
            return render_template('qr_result.html', user_info=None, ticket_status="Không có dữ liệu")

        try:
            data = json.loads(qr_data_string)
            ticket_code = data.get('ticket_code')
            user_id = data.get('user_id')
            event_id = data.get('event_id')

            if not all([ticket_code, user_id, event_id]):
                ticket_status = "Dữ liệu QR không hợp lệ. Thiếu thông tin cần thiết."
                flash(ticket_status, 'error')
                return render_template('qr_result.html', user_info=None, ticket_status=ticket_status)

            ticket = Ticket.query.filter_by(
                ticket_code=ticket_code,
                user_id=user_id,
                event_id=event_id
            ).first()

            if not ticket:
                ticket_status = "Vé không hợp lệ hoặc không tồn tại."
                flash(ticket_status, 'error')
                return render_template('qr_result.html', user_info=None, ticket_status=ticket_status)

            user = User.query.get(user_id)
            event = Event.query.get(event_id)

            if not user or not event:
                ticket_status = "Không tìm thấy thông tin người dùng hoặc sự kiện."
                flash(ticket_status, 'error')
                return render_template('qr_result.html', user_info=None, ticket_status=ticket_status)

            user_info = {
                "fullname": user.fullname,
                "student_id": user.student_id or user.cccd,
                "student_class": user.student_class,
                "faculty": user.faculty,
                "email": user.email,
                "event_name": event.name,
                "event_date": event.date.strftime('%d/%m/%Y'),
                "ticket_code": ticket.ticket_code
            }

            if ticket.is_used:
                ticket_status = "Vé đã được sử dụng"
                flash(ticket_status, 'warning')
            else:
                ticket_status = "Vé hợp lệ"
                ticket.is_used = True
                db.session.commit()
                flash('Vé đã được sử dụng thành công.', 'success')
            
        except json.JSONDecodeError:
            ticket_status = "Dữ liệu QR không phải JSON hợp lệ."
            flash(ticket_status, 'error')
        except Exception as e:
            db.session.rollback()
            ticket_status = f"Lỗi máy chủ: {str(e)}"
            flash(f"Lỗi máy chủ: {str(e)}", 'error')
            
    return render_template('qr_result.html', user_info=user_info, ticket_status=ticket_status)

@app.route('/admin/manage-tickets')
@login_required
@required_roles('admin', 'doan_truong')
def manage_tickets():
    tickets = Ticket.query.order_by(Ticket.booking_date.desc()).all()
    return render_template('manage_tickets.html', tickets=tickets)


@app.route('/admin/edit-ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def edit_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    event = Event.query.get_or_404(ticket.event_id)
    user = User.query.get_or_404(ticket.user_id)
    user_info_json = json.loads(ticket.user_info_json) if ticket.user_info_json else {}

    if request.method == 'POST':
        try:
            ticket.is_used = request.form.get('is_used') == 'on'
            ticket.is_approved = request.form.get('is_approved') == 'on'
            
            user_info = {
                "fullname": request.form.get('fullname', user_info_json.get('fullname', '')),
                "student_id": request.form.get('student_id', user_info_json.get('student_id', '')),
                "student_class": request.form.get('student_class', user_info_json.get('student_class', '')),
                "faculty": request.form.get('faculty', user_info_json.get('faculty', '')),
                "email": request.form.get('email', user_info_json.get('email', ''))
            }
            ticket.user_info_json = json.dumps(user_info)

            if request.form.get('event_info_json'):
                ticket.event_info_json = request.form.get('event_info_json')

            db.session.commit()
            flash('Vé đã được cập nhật thành công!', 'success')
            return redirect(url_for('manage_tickets'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật vé: {e}', 'danger')
            return redirect(url_for('edit_ticket', ticket_id=ticket_id))

    return render_template('edit_tickets.html', ticket=ticket, event=event, user=user, user_info_json=user_info_json)


@app.route('/admin/delete-ticket/<int:ticket_id>', methods=['POST'])
@login_required
@required_roles('admin', 'doan_truong')
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    try:
        event = Event.query.get(ticket.event_id)
        if event and not ticket.is_used:
            event.available_tickets += 1
        
        ticket_filename = f"{ticket.ticket_code}.png"
        ticket_path = os.path.join(app.root_path, 'static', 'images', 'tickets', ticket_filename)
        if os.path.exists(ticket_path):
            os.remove(ticket_path)

        db.session.delete(ticket)
        db.session.commit()
        flash('Vé đã được xóa thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa vé: {e}', 'danger')
        
    return redirect(url_for('manage_tickets'))

@app.route('/admin/update-ticket-status/<int:ticket_id>', methods=['POST'])
@login_required
@required_roles('admin', 'doan_truong')
def update_ticket_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    new_status = request.form.get('status')
    
    if new_status == 'used':
        ticket.is_used = True
        flash('Đã cập nhật trạng thái vé thành "Đã sử dụng".', 'success')
    elif new_status == 'unused':
        ticket.is_used = False
        flash('Đã cập nhật trạng thái vé thành "Chưa sử dụng".', 'success')
    
    db.session.commit()
    return redirect(url_for('manage_tickets'))

@app.route('/admin/manage-users')
@login_required
@required_roles('admin', 'doan_truong')
def manage_users():
    if current_user.role == 'admin':
        users = User.query.all()
    else:  # doan_truong
        users = User.query.filter_by(role='sinh_vien').all()
    return render_template('manage_users.html', users=users)

@app.route('/admin/add-user', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        student_id = request.form.get('student_id')
        cccd = request.form.get('cccd')
        phone = request.form.get('phone')
        faculty = request.form.get('faculty')
        student_class = request.form.get('student_class')
        dob_str = request.form.get('dob')
        course = request.form.get('course')
        security_question = request.form.get('security_question')
        security_answer = request.form.get('security_answer')

        if not security_question or not security_answer:
            flash('Vui lòng chọn câu hỏi bảo mật và cung cấp câu trả lời.', 'danger')
            return redirect(url_for('add_user'))

        if current_user.role == 'doan_truong' and role != 'sinh_vien':
            flash('Bạn chỉ có quyền thêm người dùng với vai trò sinh viên.', 'danger')
            return redirect(url_for('add_user'))

        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại.', 'danger')
            return redirect(url_for('add_user'))
        if email and User.query.filter_by(email=email).first():
            flash('Email đã tồn tại.', 'danger')
            return redirect(url_for('add_user'))
        if cccd and User.query.filter_by(cccd=cccd).first():
            flash('Số CCCD đã tồn tại.', 'danger')
            return redirect(url_for('add_user'))
        if student_id and User.query.filter_by(student_id=student_id).first():
            flash('Mã sinh viên đã tồn tại.', 'danger')
            return redirect(url_for('add_user'))

        try:
            dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            new_user = User(
                username=username,
                role=role,
                fullname=fullname,
                email=email,
                student_id=student_id,
                cccd=cccd,
                phone=phone,
                faculty=faculty,
                student_class=student_class,
                dob=dob,
                course=course,
                security_question=security_question
            )
            new_user.set_password(password)
            new_user.set_security_answer(security_answer)
            db.session.add(new_user)
            db.session.commit()
            flash('Người dùng đã được thêm thành công!', 'success')
            return redirect(url_for('manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi thêm người dùng: {e}', 'danger')
            return redirect(url_for('add_user'))
            
    return render_template('add_user.html', security_questions=SECURITY_QUESTIONS)

@app.route('/admin/edit-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@required_roles('admin', 'doan_truong')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if current_user.role == 'doan_truong' and user.role != 'sinh_vien':
        flash('Bạn chỉ có quyền chỉnh sửa người dùng với vai trò sinh viên.', 'danger')
        return redirect(url_for('manage_users'))

    if request.method == 'POST':
        try:
            existing_user_by_username = User.query.filter_by(username=request.form.get('username')).first()
            if existing_user_by_username and existing_user_by_username.id != user.id:
                flash('Tên đăng nhập đã tồn tại.', 'danger')
                return redirect(url_for('edit_user', user_id=user.id))
            
            existing_user_by_email = User.query.filter_by(email=request.form.get('email')).first()
            if existing_user_by_email and existing_user_by_email.id != user.id:
                flash('Email đã tồn tại.', 'danger')
                return redirect(url_for('edit_user', user_id=user.id))
            
            existing_user_by_cccd = User.query.filter_by(cccd=request.form.get('cccd')).first()
            if existing_user_by_cccd and existing_user_by_cccd.id != user.id:
                flash('Số CCCD đã tồn tại.', 'danger')
                return redirect(url_for('edit_user', user_id=user.id))

            existing_user_by_studentid = User.query.filter_by(student_id=request.form.get('student_id')).first()
            if existing_user_by_studentid and existing_user_by_studentid.id != user.id:
                flash('Mã sinh viên đã tồn tại.', 'danger')
                return redirect(url_for('edit_user', user_id=user.id))

            if current_user.role == 'doan_truong' and request.form.get('role') != 'sinh_vien':
                flash('Bạn chỉ có quyền chỉnh sửa vai trò thành sinh viên.', 'danger')
                return redirect(url_for('edit_user', user_id=user.id))

            user.username = request.form.get('username')
            user.role = request.form.get('role')
            user.fullname = request.form.get('fullname')
            user.email = request.form.get('email')
            user.student_id = request.form.get('student_id')
            user.cccd = request.form.get('cccd')
            user.phone = request.form.get('phone')
            user.faculty = request.form.get('faculty')
            user.student_class = request.form.get('student_class')
            
            dob_str = request.form.get('dob')
            user.dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            user.course = request.form.get('course')
            
            security_question = request.form.get('security_question')
            security_answer = request.form.get('security_answer')
            if security_question and security_answer:
                user.security_question = security_question
                user.set_security_answer(security_answer)
            
            new_password = request.form.get('password')
            if new_password:
                user.set_password(new_password)
            
            db.session.commit()
            flash('Thông tin người dùng đã được cập nhật!', 'success')
            return redirect(url_for('manage_users'))
        except IntegrityError:
            db.session.rollback()
            flash('Lỗi cập nhật: Tên đăng nhập, email hoặc CCCD đã tồn tại.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật người dùng: {e}', 'danger')

    return render_template('edit_user.html', user=user, security_questions=SECURITY_QUESTIONS)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@required_roles('admin', 'doan_truong')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if current_user.role == 'doan_truong' and user.role != 'sinh_vien':
        flash('Bạn chỉ có quyền xóa người dùng với vai trò sinh viên.', 'danger')
        return redirect(url_for('manage_users'))

    if user.id == current_user.id:
        flash('Bạn không thể tự xóa tài khoản của mình.', 'danger')
        return redirect(url_for('manage_users'))
    
    try:
        tickets_to_delete = Ticket.query.filter_by(user_id=user_id).all()
        for ticket in tickets_to_delete:
            if not ticket.is_used:
                event = Event.query.get(ticket.event_id)
                if event:
                    event.available_tickets += 1
            
            ticket_path = os.path.join(app.root_path, 'static', 'images', 'tickets', f"{ticket.ticket_code}.png")
            if os.path.exists(ticket_path):
                os.remove(ticket_path)
            db.session.delete(ticket)

        db.session.delete(user)
        db.session.commit()
        flash('Người dùng và tất cả các vé liên quan đã được xóa thành công.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa người dùng: {e}', 'danger')

    return redirect(url_for('manage_users'))

@app.route('/events')
@login_required
@required_roles('sinh_vien')
def events():
    events = Event.query.all()
    return render_template('events.html', events=events)

@app.route('/event/<int:event_id>')
@login_required
@required_roles('sinh_vien')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_detail.html', event=event)

# 5. Khởi chạy ứng dụng và tạo dữ liệu ban đầu
def create_initial_data():
    with app.app_context(): 
        db.create_all()
        
        tickets_dir = os.path.join(app.root_path, 'static', 'images', 'tickets')
        os.makedirs(tickets_dir, exist_ok=True)
        
        event_images_dir = os.path.join(app.root_path, 'static', 'Uploads', 'event_images')
        os.makedirs(event_images_dir, exist_ok=True)

        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                role='admin',
                fullname='Quản trị viên',
                security_question=SECURITY_QUESTIONS[0]
            )
            admin_user.set_password('admin123')
            admin_user.set_security_answer('adminanswer')
            db.session.add(admin_user)

        if not User.query.filter_by(username='doantruong').first():
            doantruong_user = User(
                username='doantruong',
                role='doan_truong',
                fullname='Đoàn trường',
                security_question=SECURITY_QUESTIONS[0]
            )
            doantruong_user.set_password('doantruong123')
            doantruong_user.set_security_answer('doananswer')
            db.session.add(doantruong_user)
        
        if not User.query.filter_by(username='sinhvien1').first():
            student_user = User(
                username='sinhvien1', 
                role='sinh_vien', 
                fullname='Nguyễn Văn A', 
                student_id='20211111', 
                faculty='Công nghệ thông tin', 
                student_class='K66 CNTT', 
                email='a.nguyen@example.com', 
                phone='0912345678',
                dob=datetime.date(2003, 5, 10),
                course='K66',
                security_question=SECURITY_QUESTIONS[0]
            )
            student_user.set_password('123456')
            student_user.set_security_answer('school1')
            db.session.add(student_user)
        
        if not User.query.filter_by(username='sinhvien2').first():
            student_user_cccd = User(
                username='sinhvien2', 
                role='sinh_vien', 
                fullname='Trần Thị B', 
                cccd='012345678901', 
                faculty='Điện tử viễn thông', 
                student_class='K67 ĐTVT', 
                email='b.tran@example.com', 
                phone='0987654321',
                dob=datetime.date(2004, 8, 20),
                course='K67',
                security_question=SECURITY_QUESTIONS[1]
            )
            student_user_cccd.set_password('123456')
            student_user_cccd.set_security_answer('pet1')
            db.session.add(student_user_cccd)

        if not Event.query.first():
            events = [
                Event(
                    name='Hội thảo công nghệ',
                    date=datetime.datetime(2025, 10, 15),
                    location='Hội trường A',
                    description='Hội thảo về công nghệ AI',
                    total_tickets=100,
                    available_tickets=100,
                    image_url='https://sieuviet.vn/hm_content/uploads/anh-tin-tuc/1_8.jpg'
                ),
                Event(
                    name='Đêm nhạc sinh viên',
                    date=datetime.datetime(2025, 11, 20),
                    location='Sân khấu ngoài trời',
                    description='Đêm nhạc với các ban nhạc sinh viên',
                    total_tickets=200,
                    available_tickets=200,
                    image_url='https://media-cdn-v2.laodong.vn/storage/newsportal/2024/9/19/1396783/Dai-Hoc-Thang-Long-1-04.jpg'
                ),
                Event(
                    name='Ngày hội thể thao',
                    date=datetime.datetime(2025, 12, 5),
                    location='Sân vận động DNU',
                    description='Giải đấu thể thao sinh viên',
                    total_tickets=150,
                    available_tickets=150,
                    image_url='https://doanthidiem.edu.vn/wp-content/uploads/2021/01/10-7.jpg'
                ),
            ]
            db.session.add_all(events)
            
        default_image_path = os.path.join(UPLOAD_FOLDER, 'default_event.jpg')
        if not os.path.exists(default_image_path):
            img = Image.new('RGB', (800, 400), color='gray')
            d = ImageDraw.Draw(img)
            try:
                fnt = ImageFont.truetype("arial.ttf", 40)
            except IOError:
                fnt = ImageFont.load_default()
            d.text((50, 150), "Ảnh sự kiện mặc định", fill=(255, 255, 255), font=fnt)
            img.save(default_image_path)
        
        db.session.commit()

if __name__ == '__main__':
    create_initial_data()
    app.run(debug=True, host='0.0.0.0')