from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO
from sqlalchemy import case, func, distinct, extract, and_, event, or_
from unidecode import unidecode
import pandas as pd
import openpyxl
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

# Cấu hình logging

if not os.path.exists('logs'):
    os.mkdir('logs')
    
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

db = SQLAlchemy(app)

# Cấu hình upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Tạo thư mục uploads nếu chưa có
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Model để lưu dữ liệu
class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stt = db.Column(db.Integer)
    ma_lo = db.Column(db.String(20))
    tt_hd = db.Column(db.String(20))
    ma_khach_hang = db.Column(db.String(50))
    ten_khach_hang = db.Column(db.String(100), index=True)
    dia_chi = db.Column(db.String(200))
    so_dien_thoai = db.Column(db.String(20))  # Thêm cột số điện thoại
    kwh = db.Column(db.String(50))
    tien_dien = db.Column(db.Float)
    vat = db.Column(db.Float)
    tong_tien = db.Column(db.Float)
    tai_khoan_quan_ly = db.Column(db.String(80))  # Thêm trường này
    trang_thai = db.Column(db.String(50))
    ngay_thu = db.Column(db.DateTime, nullable=True)

# Model User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(100))  # Thêm trường Tên người dùng
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # Đảm bảo column này tồn tại
    is_active = db.Column(db.Boolean, default=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Quan hệ với users dưới quyền
    subordinates = db.relationship('User', 
                                 backref=db.backref('manager', remote_side=[id]),
                                 lazy='dynamic',
                                 foreign_keys=[manager_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_manager(self):
        return self.role == 'manager'

def init_db():
    with app.app_context():
        # Tạo function unidecode cho SQLite
        def sqlite_unidecode(string):
            return unidecode(string) if string else None
        
        # Đăng ký function với SQLite
        engine = db.engine  # Sử dụng .engine thay vì .get_engine()
        engine.connect().connection.create_function("unidecode", 1, sqlite_unidecode)
        
        # Tạo bảng và admin
        db.create_all()
        create_admin()

# Decorator để kiểm tra quyền admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session['username']).first()
        if not user or not user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session['username']).first()
        if not user or not (user.is_admin or user.is_manager):
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.context_processor
def utility_processor():
    return {
        'datetime': datetime
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        full_name = request.form.get('full_name', '')  # Lấy tên người dùng
        email = request.form['email']
        password = request.form['password']
        
        # Kiểm tra tên người dùng đã tồn tại chưa
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Kiểm tra email đã được đăng ký chưa
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Tạo người dùng mới
        user = User(username=username, full_name=full_name, email=email)
        user.set_password(password)
        
        # Thêm người dùng vào cơ sở dữ liệu
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact admin.')
                return redirect(url_for('login'))
            
            session['username'] = username
            if user.is_admin:
                return redirect(url_for('main_dashboard'))
            return redirect(url_for('main_dashboard'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']
        
        if email != user.email:
            if User.query.filter_by(email=email).first():
                flash('Email already exists')
                return redirect(url_for('profile'))
            user.email = email
        
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash('Profile updated successfully')
        
    return render_template('profile.html', user=user)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    users = User.query.all()
    current_user = User.query.filter_by(username=session['username']).first()
    return render_template('admin/dashboard.html', 
                         users=users,
                         user=current_user)  

# Thêm các route mới cho admin
@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    current_user = User.query.filter_by(username=session['username']).first()
    
    if request.method == 'POST':
        try:
            # In ra form data để debug
            app.logger.info(f"Form data received: {request.form}")
            
            full_name = request.form.get('full_name', '')
            email = request.form.get('email', '')
            role = request.form.get('role', '')
            manager_id = request.form.get('manager_id', '')
            is_active = 'is_active' in request.form
            new_password = request.form.get('new_password', '')

            app.logger.info(f"Current user role: {user.role}, New role: {role}")
            app.logger.info(f"Manager ID from form: '{manager_id}' (type: {type(manager_id)})")

            # Validation
            if not email or not role:
                flash('Email và Role là bắt buộc')
                return redirect(url_for('admin_edit_user', user_id=user_id))

            # Cập nhật thông tin
            user.full_name = full_name
            user.email = email
            user.role = role
            user.is_active = is_active

            if new_password:
                user.set_password(new_password)

            # Handle manager_id carefully
            if role != 'admin':
                if manager_id and manager_id.strip() and manager_id != '':
                    try:
                        new_manager_id = int(manager_id)
                        
                        # Validation 1: Không thể tự làm manager của mình
                        if new_manager_id == user.id:
                            app.logger.error(f"User cannot be their own manager")
                            flash('Người dùng không thể là quản lý của chính mình')
                            return redirect(url_for('admin_edit_user', user_id=user_id))
                        
                        # Validation 2: Manager phải tồn tại và có role admin/manager
                        manager = User.query.get(new_manager_id)
                        if not manager:
                            app.logger.error(f"Manager with id {new_manager_id} not found")
                            flash('Tài khoản quản lý không tồn tại')
                            return redirect(url_for('admin_edit_user', user_id=user_id))
                        
                        if manager.role not in ['admin', 'manager']:
                            app.logger.error(f"User {new_manager_id} is not a manager/admin")
                            flash('Tài khoản được chọn không phải là quản lý')
                            return redirect(url_for('admin_edit_user', user_id=user_id))
                        
                        # Validation 3: Kiểm tra circular reference (A -> B -> A)
                        temp_manager = manager
                        while temp_manager.manager_id:
                            if temp_manager.manager_id == user.id:
                                app.logger.error(f"Circular reference detected")
                                flash('Không thể tạo vòng lặp phân quyền')
                                return redirect(url_for('admin_edit_user', user_id=user_id))
                            temp_manager = User.query.get(temp_manager.manager_id)
                            if not temp_manager:
                                break
                        
                        user.manager_id = new_manager_id
                        app.logger.info(f"Setting manager_id to: {user.manager_id}")
                        
                    except (ValueError, TypeError) as e:
                        app.logger.error(f"Invalid manager_id: {manager_id}, error: {e}")
                        flash('ID quản lý không hợp lệ')
                        return redirect(url_for('admin_edit_user', user_id=user_id))
                else:
                    user.manager_id = None
            else:
                user.manager_id = None

            # Commit changes
            db.session.commit()
            app.logger.info(f"User updated successfully. Role after update: {user.role}")

            flash('Cập nhật user thành công')
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating user: {str(e)}", exc_info=True)
            flash(f'Lỗi khi cập nhật user: {str(e)}')
            return redirect(url_for('admin_edit_user', user_id=user_id))
    
    # GET request
    managers = User.query.filter(
        User.role.in_(['admin', 'manager']),
        User.id != user_id
    ).all()
    
    return render_template('admin/edit_user.html', 
                         user=user, 
                         current_user=current_user,
                         managers=managers)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == session['username']:
        flash('You cannot delete your own account')
        return redirect(url_for('admin_dashboard'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully')
    return redirect(url_for('admin_dashboard'))

@app.route('/dashboard')
def main_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    
    # Xây dựng query cơ bản
    query = SalesData.query

    # Lọc theo quyền người dùng
    if not user.is_admin:
        if user.is_manager:
            subordinate_usernames = [u.username for u in user.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            query = query.filter(SalesData.tai_khoan_quan_ly == user.username)

    # Thống kê tổng quan
    total_revenue = query.with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
    total_paid = query.filter_by(trang_thai='Đã thanh toán').with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
    total_unpaid = query.filter_by(trang_thai='Chưa thanh toán').with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
    
    total_invoices = query.count()
    total_paid_invoices = query.filter_by(trang_thai='Đã thanh toán').count()
    total_unpaid_invoices = query.filter_by(trang_thai='Chưa thanh toán').count()
    
    completion_rate = (total_paid_invoices / total_invoices * 100) if total_invoices > 0 else 0

    # Thêm thống kê theo ngày cho biểu đồ
    daily_stats = {}
    sales_data = query.all()
    for record in sales_data:
        if record.ngay_thu:
            date_str = record.ngay_thu.strftime('%Y-%m-%d')
            if date_str not in daily_stats:
                daily_stats[date_str] = {'paid': 0, 'count': 0}
            if record.trang_thai == 'Đã thanh toán':
                daily_stats[date_str]['paid'] += record.tong_tien
            daily_stats[date_str]['count'] += 1

    # Lấy 7 ngày gần nhất
    chart_dates = sorted(daily_stats.keys(), reverse=True)[:7]
    chart_dates.reverse()
    chart_data = {
        'dates': chart_dates,
        'amounts': [daily_stats[date]['paid'] for date in chart_dates],
        'counts': [daily_stats[date]['count'] for date in chart_dates]
    }

    # Thêm tỷ lệ thu tiền theo mã lộ
    ma_lo_stats = {}
    for record in sales_data:
        if record.ma_lo not in ma_lo_stats:
            ma_lo_stats[record.ma_lo] = {'total': 0, 'paid': 0}
        ma_lo_stats[record.ma_lo]['total'] += record.tong_tien
        if record.trang_thai == 'Đã thanh toán':
            ma_lo_stats[record.ma_lo]['paid'] += record.tong_tien

    pie_chart_data = {
        'labels': list(ma_lo_stats.keys()),
        'paid_percentages': [
            round((stats['paid'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0 
            for stats in ma_lo_stats.values()
        ]
    }

    # Giao dịch gần đây
    recent_transactions = query.order_by(SalesData.ngay_thu.desc()).limit(5).all()

    return render_template('main_dashboard.html',
                         user=user,
                         total_revenue=total_revenue,
                         total_paid=total_paid,
                         total_unpaid=total_unpaid,
                         total_invoices=total_invoices,
                         total_paid_invoices=total_paid_invoices,
                         total_unpaid_invoices=total_unpaid_invoices,
                         completion_rate=completion_rate,
                         recent_transactions=recent_transactions,
                         chart_data=chart_data,
                         pie_chart_data=pie_chart_data)


@app.route('/admin/import', methods=['GET', 'POST'])
@manager_required  # Cho phép cả admin và manager
def import_data():
    user = User.query.filter_by(username=session['username']).first()
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        selected_user = request.form.get('selected_user')  # Thêm trường chọn user
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if not selected_user:
            flash('Please select a user to manage this data')
            return redirect(request.url)
        
        # Kiểm tra quyền của manager
        if not user.is_admin:
            subordinate_usernames = [u.username for u in user.subordinates]
            if selected_user not in subordinate_usernames and selected_user != user.username:
                flash('Không có quyền assign dữ liệu cho user này')
                return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                df = pd.read_excel(filepath)
                
                # Kiểm tra các cột bắt buộc
                required_columns = ['STT', 'Mã lộ', 'TT HĐ', 'Mã Khách hàng', 
                                  'Tên Khách hàng', 'Địa chỉ', 'Kwh', 
                                  'Tiền điện', 'VAT', 'Tổng tiền']
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    flash(f'File thiếu các cột: {", ".join(missing_columns)}')
                    os.remove(filepath)
                    return redirect(url_for('import_data'))
                
                for index, row in df.iterrows():
                    # Kiểm tra dữ liệu trùng lặp
                    existing_data = SalesData.query.filter_by(
                        ma_khach_hang=str(row['Mã Khách hàng']),
                        ma_lo=str(row['Mã lộ'])
                    ).first()
                    
                    if existing_data:
                        flash(f"Dữ liệu của khách hàng {row['Mã Khách hàng']} - Mã lộ {row['Mã lộ']} đã tồn tại.")
                        continue
                    
                    try:
                        # Chuyển đổi và kiểm tra dữ liệu số
                        tien_dien = float(row['Tiền điện'])
                        vat = float(row['VAT'])
                        tong_tien = float(row['Tổng tiền'])
                    except (ValueError, TypeError):
                        flash(f'Lỗi dữ liệu số tại dòng {index + 2}')
                        continue
                    
                    # Lấy số điện thoại nếu cột tồn tại
                    so_dien_thoai = ''
                    if 'Số điện thoại' in df.columns and pd.notna(row['Số điện thoại']):
                        so_dien_thoai = str(row['Số điện thoại'])
                    
                    # Tạo bản ghi mới
                    data = SalesData(
                        stt=row['STT'],
                        ma_lo=str(row['Mã lộ']),
                        tt_hd=str(row['TT HĐ']),
                        ma_khach_hang=str(row['Mã Khách hàng']),
                        ten_khach_hang=str(row['Tên Khách hàng']),
                        dia_chi=str(row['Địa chỉ']),
                        so_dien_thoai=so_dien_thoai,
                        kwh=str(row['Kwh']),
                        tien_dien=tien_dien,
                        vat=vat,
                        tong_tien=tong_tien,
                        tai_khoan_quan_ly=selected_user,
                        trang_thai='Chưa thanh toán'
                    )
                    db.session.add(data)
                
                db.session.commit()
                flash('Import dữ liệu thành công')
                
            except Exception as e:
                db.session.rollback()
                flash(f'Lỗi khi import dữ liệu: {str(e)}')
            finally:
                # Xóa file tạm sau khi xử lý xong
                if os.path.exists(filepath):
                    os.remove(filepath)
                
            return redirect(url_for('view_data'))
    
    # Lấy danh sách users cho form dựa trên quyền
    if user.is_admin:
        # Admin có thể assign cho tất cả users
        users = User.query.filter(User.role != 'admin').all()
    else:
        # Manager chỉ có thể assign cho users dưới quyền
        users = list(user.subordinates)
    
    return render_template('admin/import.html', users=users)

# Hàm kiểm tra file extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/export', methods=['GET'])
def export_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Lấy thông tin người dùng đang đăng nhập
    user = User.query.filter_by(username=session['username']).first()

    # Lấy thông tin tìm kiếm từ request
    search_user = request.args.get('search_user', '', type=str)
    search_ma_lo = request.args.get('search_ma_lo', '', type=str)
    search_trang_thai = request.args.get('search_trang_thai', '', type=str)
    search_ten_khach_hang = request.args.get('search_ten_khach_hang', '', type=str).strip()
    search_ngay_thu = request.args.get('search_ngay_thu', '', type=str)

    # Xây dựng query cơ bản
    query = SalesData.query

    # Xử lý tìm kiếm theo tài khoản quản lý
    if search_user:
        if User.query.filter_by(username=search_user, role='manager').first():
            # Nếu tìm theo manager, chỉ lấy dữ liệu của users dưới quyền
            manager = User.query.filter_by(username=search_user).first()
            subordinate_usernames = [u.username for u in manager.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            # Nếu tìm theo user thường
            query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
    elif not user.is_admin:  # Nếu không có tìm kiếm và không phải admin
        if user.is_manager:
            # Manager sẽ thấy dữ liệu của các user dưới quyền
            subordinate_usernames = [u.username for u in user.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            # User thường chỉ thấy dữ liệu của mình
            query = query.filter(SalesData.tai_khoan_quan_ly == user.username)
    
    if search_ma_lo:
        query = query.filter(SalesData.ma_lo.like(f'%{search_ma_lo}%'))

    if search_trang_thai:
        query = query.filter(SalesData.trang_thai == search_trang_thai)

    if search_ten_khach_hang:
        search_pattern = '%'.join(search_ten_khach_hang)
        query = query.filter(SalesData.ten_khach_hang.ilike(f'%{search_pattern}%'))

    if search_ngay_thu:
        try:
            search_ngay_thu_date = datetime.strptime(search_ngay_thu, '%Y-%m-%d').date()
            query = query.filter(SalesData.ngay_thu >= search_ngay_thu_date)
            query = query.filter(SalesData.ngay_thu < search_ngay_thu_date + timedelta(days=1))
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('view_data'))

    # Truy vấn dữ liệu sau khi áp dụng bộ lọc
    data = query.all()
    
    # Debug: In số lượng dữ liệu
    print(f"Export debug - User: {user.username}, Role: {user.role}")
    print(f"Export debug - Found {len(data)} records")
    print(f"Export debug - Search params: user={search_user}, ma_lo={search_ma_lo}, trang_thai={search_trang_thai}")

    # Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Filtered Sales Data"

    # Tiêu đề cột
    ws.append(['STT', 'Mã Lộ', 'Mã Khách Hàng', 'Tên Khách Hàng', 'Địa Chỉ', 'Số Điện Thoại', 'Tổng Tiền', 'Tài Khoản Quản Lý', 'Trạng Thái', 'Ngày thu'])

    # Ghi dữ liệu vào file Excel
    for row in data:
        so_dien_thoai = getattr(row, 'so_dien_thoai', '')  # Lấy số điện thoại nếu có, nếu không thì để trống
        ws.append([row.stt, row.ma_lo, row.ma_khach_hang, row.ten_khach_hang, row.dia_chi, so_dien_thoai, row.tong_tien, row.tai_khoan_quan_ly, row.trang_thai, row.ngay_thu])

    # Lưu file Excel vào bộ nhớ tạm
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Trả về file Excel
    return Response(output.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={
        'Content-Disposition': 'attachment; filename=filtered_sales_data.xlsx'
    })

def get_hierarchical_users():
    """Hàm lấy danh sách users theo cấp bậc"""
    # Lấy tất cả managers (không bao gồm admin)
    managers = User.query.filter_by(role='manager').all()
    
    hierarchical_users = []
    
    for manager in managers:
        # Thêm manager
        hierarchical_users.append({
            'id': manager.id,
            'username': manager.username,
            'role': 'manager',
            'level': 0  # Level 0 cho manager
        })
        
        # Thêm các users dưới quyền của manager
        for user in manager.subordinates:
            if user.role == 'user':  # Chỉ lấy user thường
                hierarchical_users.append({
                    'id': user.id,
                    'username': user.username,
                    'role': 'user',
                    'level': 1,  # Level 1 cho user dưới quyền
                    'manager': manager.username
                })
    
    # Thêm các user không có manager
    independent_users = User.query.filter(
        User.role == 'user',
        User.manager_id.is_(None)
    ).all()
    
    for user in independent_users:
        hierarchical_users.append({
            'id': user.id,
            'username': user.username,
            'role': 'user',
            'level': 0,  # Level 0 cho user độc lập
            'manager': None
        })
    
    return hierarchical_users

@app.route('/data', methods=['GET', 'POST'])
def view_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    
    # Chuẩn bị danh sách users có cấu trúc phân cấp
    if user.is_admin:
        # Lấy tất cả managers
        managers = User.query.filter_by(role='manager').all()
        users_list = []
        
        # Thêm managers và users của họ
        for manager in managers:
            # Thêm manager
            users_list.append({
                'username': manager.username,
                'role': 'manager',
                'manager_username': None
            })
            
            # Thêm users của manager này
            for sub_user in manager.subordinates:
                users_list.append({
                    'username': sub_user.username,
                    'role': 'user',
                    'manager_username': manager.username
                })
        
        # Thêm users không có manager
        independent_users = User.query.filter(
            User.role == 'user',
            User.manager_id.is_(None)
        ).all()
        
        for ind_user in independent_users:
            users_list.append({
                'username': ind_user.username,
                'role': 'user',
                'manager_username': None
            })
            
    elif user.is_manager:
        # Tạo danh sách bắt đầu với manager
        users_list = [{
            'username': user.username,
            'role': 'manager',
            'manager_username': None
        }]
        
        # Thêm users dưới quyền của manager
        users_list.extend([{
            'username': sub_user.username,
            'role': 'user',
            'manager_username': user.username
        } for sub_user in user.subordinates])
    else:
        # User thường chỉ thấy chính mình
        users_list = [{
            'username': user.username,
            'role': 'user',
            'manager_username': None
        }]

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_user = request.args.get('search_user', '', type=str)
    search_ma_lo = request.args.get('search_ma_lo', '', type=str)
    search_trang_thai = request.args.get('search_trang_thai', '', type=str)
    search_ten_khach_hang = request.args.get('search_ten_khach_hang', '', type=str).strip()
    search_ngay_thu = request.args.get('search_ngay_thu', '', type=str)

    if request.method == 'POST':
        # Kiểm tra nếu user không phải admin và không phải manager thì không cho xóa
        if not (user.is_admin or user.is_manager):
            abort(403)
        
        selected_ids = request.form.getlist('selected_ids')
        deleted_any = False  # Cờ kiểm tra xem có bản ghi nào đã được xóa không
        try:
            for record_id in selected_ids:
                record = SalesData.query.get(record_id)
                if record:
                    # Nếu là manager, chỉ cho phép xóa dữ liệu của users dưới quyền
                    if user.is_manager and not user.is_admin:
                        subordinate_usernames = [u.username for u in user.subordinates]
                        if record.tai_khoan_quan_ly not in subordinate_usernames:
                            flash(f'Không có quyền xóa hóa đơn {record_id}', 'error')
                            continue

                    # Kiểm tra điều kiện trạng thái
                    if record.trang_thai == 'Đã thanh toán':
                        flash(f'Hóa đơn {record_id} đã được thanh toán, không thể xóa.', 'error')
                        continue  # Bỏ qua việc xóa bản ghi này
                    
                    db.session.delete(record)
                    deleted_any = True  # Đánh dấu là đã xóa ít nhất 1 bản ghi
                    
            if deleted_any:  # Chỉ hiển thị thông báo thành công nếu có bản ghi được xóa
                db.session.commit()
                flash('Đã xóa thành công.')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting records: {str(e)}', 'error')
        return redirect(url_for('view_data', page=page, per_page=per_page))
    
    # Xây dựng query cơ bản
    query = SalesData.query

    # Xử lý tìm kiếm theo tài khoản quản lý
    if search_user:
        if User.query.filter_by(username=search_user, role='manager').first():
            # Nếu tìm theo manager, chỉ lấy dữ liệu của users dưới quyền
            manager = User.query.filter_by(username=search_user).first()
            subordinate_usernames = [u.username for u in manager.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            # Nếu tìm theo user thường
            query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
    elif not user.is_admin:  # Nếu không có tìm kiếm và không phải admin
        if user.is_manager:
            # Manager sẽ thấy dữ liệu của các user dưới quyền
            subordinate_usernames = [u.username for u in user.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            # User thường chỉ thấy dữ liệu của mình
            query = query.filter(SalesData.tai_khoan_quan_ly == user.username)

    # Áp dụng các điều kiện tìm kiếm khác
    if search_ma_lo:
        query = query.filter(SalesData.ma_lo.like(f'%{search_ma_lo}%'))

    if search_trang_thai:
        query = query.filter(SalesData.trang_thai == search_trang_thai)

    if search_ten_khach_hang:
        search_pattern = '%'.join(search_ten_khach_hang)
        query = query.filter(SalesData.ten_khach_hang.ilike(f'%{search_pattern}%'))

    if search_ngay_thu:
        try:
            search_ngay_thu_date = datetime.strptime(search_ngay_thu, '%Y-%m-%d').date()
            query = query.filter(
                SalesData.ngay_thu >= search_ngay_thu_date,
                SalesData.ngay_thu < search_ngay_thu_date + timedelta(days=1)
            )
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')

    try:
        # Phân trang dữ liệu
        data = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Tính tổng tiền
        total_amount = query.with_entities(db.func.sum(SalesData.tong_tien)).scalar() or 0
        
        # Tính tổng số hóa đơn
        total_invoices = query.count()
        
        # Lấy danh sách mã lộ
        if user.is_admin:
            if search_user:  # Nếu đã chọn user cụ thể
                selected_user = User.query.filter_by(username=search_user).first()
                if selected_user:
                    if selected_user.role == 'manager':
                        # Nếu chọn manager, lấy mã lộ của tất cả user dưới quyền
                        subordinate_usernames = [u.username for u in selected_user.subordinates]
                        ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                            SalesData.tai_khoan_quan_ly.in_(subordinate_usernames)
                        )
                    else:
                        # Nếu chọn user thường, chỉ lấy mã lộ của user đó
                        ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                            SalesData.tai_khoan_quan_ly == search_user
                        )
            else:
                # Nếu không chọn user, lấy tất cả mã lộ
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct()

        elif user.is_manager:
            subordinate_usernames = [u.username for u in user.subordinates]
            if search_user and search_user in subordinate_usernames:
                # Nếu manager chọn một user cụ thể trong nhóm của mình
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                    SalesData.tai_khoan_quan_ly == search_user
                )
            else:
                # Nếu không chọn user cụ thể, lấy mã lộ của tất cả user dưới quyền
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                    SalesData.tai_khoan_quan_ly.in_(subordinate_usernames)
                )
        else:
            # User thường chỉ thấy mã lộ của mình
            ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                SalesData.tai_khoan_quan_ly == user.username
            )

        ma_lo_list = [item[0] for item in ma_lo_query.all()]
        
        return render_template('admin/view_data.html',
                         user=user,
                         users=users_list,
                         data=data,
                         search_user=search_user,
                         search_ma_lo=search_ma_lo,
                         ma_lo_list=ma_lo_list,
                         search_trang_thai=search_trang_thai,
                         search_ten_khach_hang=search_ten_khach_hang,
                         search_ngay_thu=search_ngay_thu,
                         total_amount=total_amount,
                         total_invoices=total_invoices,
                         per_page=per_page)
    except Exception as e:
        flash(f'Error loading data: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/report', methods=['GET'])
def report():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    search_user = request.args.get('search_user', '', type=str)
    users_list = []
    if user.is_admin:
        # Logic cho admin giữ nguyên
        managers = User.query.filter_by(role='manager').all()
        for manager in managers:
            users_list.append({
                'username': manager.username,
                'role': 'manager',
                'manager_username': None
            })
            
            subordinates = User.query.filter_by(manager_id=manager.id).all()
            for sub_user in subordinates:
                users_list.append({
                    'username': sub_user.username,
                    'role': 'user',
                    'manager_username': manager.username
                })
        
        # Thêm các user độc lập
        independent_users = User.query.filter(
            User.role == 'user',
            User.manager_id.is_(None)
        ).all()
        
        for ind_user in independent_users:
            users_list.append({
                'username': ind_user.username,
                'role': 'user',
                'manager_username': None
            })    
    elif user.role == 'manager':  
        # Thêm manager hiện tại
        users_list.append({
            'username': user.username,
            'role': 'manager',
            'manager_username': None
        }) 
        # Lấy danh sách nhân viên của manager này
        subordinates = User.query.filter_by(manager_id=user.id).all()
        print(f"Found subordinates: {[u.username for u in subordinates]}")
        
        for sub_user in subordinates:
            users_list.append({
                'username': sub_user.username,
                'role': 'user',
                'manager_username': user.username
            })
    else:
        users_list.append({
            'username': user.username,
            'role': 'user',
            'manager_username': user.manager.username if user.manager else None
        })
    # Xây dựng query cơ bản
    query = SalesData.query
    # Xử lý tìm kiếm theo tài khoản quản lý - giống view_data
    if search_user:
        if User.query.filter_by(username=search_user, role='manager').first():
            manager = User.query.filter_by(username=search_user).first()
            subordinate_usernames = [u.username for u in manager.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
    elif not user.is_admin:
        if user.is_manager:
            subordinate_usernames = [u.username for u in user.subordinates]
            query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
        else:
            query = query.filter(SalesData.tai_khoan_quan_ly == user.username)

    report_data = query.all()
    # Tính toán số liệu cơ bản
    total_money = sum([record.tong_tien for record in report_data])
    total_paid_money = sum([record.tong_tien for record in report_data if record.trang_thai == 'Đã thanh toán'])
    total_unpaid_money = sum([record.tong_tien for record in report_data if record.trang_thai == 'Chưa thanh toán'])
    total_invoices = len(report_data)
    total_paid_invoices = len([record for record in report_data if record.trang_thai == 'Đã thanh toán'])
    total_unpaid_invoices = len([record for record in report_data if record.trang_thai == 'Chưa thanh toán'])
    # Tính toán dữ liệu cho biểu đồ theo ngày
    daily_stats = {}
    for record in report_data:
        if record.ngay_thu:
            date_str = record.ngay_thu.strftime('%Y-%m-%d')
            if date_str not in daily_stats:
                daily_stats[date_str] = {'paid': 0, 'count': 0}
            if record.trang_thai == 'Đã thanh toán':  # Chỉ tính các hóa đơn đã thanh toán
                daily_stats[date_str]['paid'] += record.tong_tien
            daily_stats[date_str]['count'] += 1
    # Sắp xếp theo ngày và lấy 7 ngày gần nhất
    chart_dates = sorted(daily_stats.keys(), reverse=True)[:7]
    chart_dates.reverse()
    chart_data = {
        'dates': chart_dates,
        'amounts': [daily_stats[date]['paid'] for date in chart_dates],
        'counts': [daily_stats[date]['count'] for date in chart_dates]
    }
    # Tính tỷ lệ thu tiền theo mã lộ
    ma_lo_stats = {}
    for record in report_data:
        if record.ma_lo not in ma_lo_stats:
            ma_lo_stats[record.ma_lo] = {
                'total': 0,
                'paid': 0
            }
        ma_lo_stats[record.ma_lo]['total'] += record.tong_tien
        if record.trang_thai == 'Đã thanh toán':
            ma_lo_stats[record.ma_lo]['paid'] += record.tong_tien
    pie_chart_data = {
        'labels': list(ma_lo_stats.keys()),
        'paid_percentages': [
            round((stats['paid'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0 
            for stats in ma_lo_stats.values()
        ]
    }
    return render_template('report.html', 
                         user=user,
                         users=users_list,
                         total_money=total_money,
                         total_paid_money=total_paid_money,
                         total_unpaid_money=total_unpaid_money,
                         total_invoices=total_invoices,
                         total_paid_invoices=total_paid_invoices,
                         total_unpaid_invoices=total_unpaid_invoices,
                         search_user=search_user,
                         chart_data=chart_data,
                         pie_chart_data=pie_chart_data)

@app.route('/print_receipt/<int:id>')
def print_receipt(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    data = SalesData.query.get_or_404(id)
    return render_template('print_receipt.html', data=data)

@app.route('/mark_as_paid/<int:id>', methods=['POST'])
def mark_as_paid(id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    try:
        data = SalesData.query.get_or_404(id)
        data.trang_thai = 'Đã thanh toán'  # Cần thêm cột trạng thái vào model
        data.ngay_thu = datetime.now()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/cancel_mark_as_paid/<int:id>', methods=['POST'])
def cancel_mark_as_paid(id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    try:
        data = SalesData.query.get_or_404(id)
        
        # Chuyển trạng thái thành "Chưa thanh toán" và xóa ngày thu
        data.trang_thai = 'Chưa thanh toán'
        data.ngay_thu = None  # Xóa ngày thu
        # Cập nhật vào cơ sở dữ liệu
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Tạo tài khoản admin đầu tiên
def create_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            role='admin',  # Set role thay vì is_admin
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

# API Endpoints
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Missing username or password'
            }), 400
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                return jsonify({
                    'success': False,
                    'message': 'Tài khoản đã bị khóa'
                }), 403
            
            # Tạo token cho phiên đăng nhập (có thể thêm JWT ở đây)
            session['username'] = username
            
            return jsonify({
                'success': True,
                'user': {
                    'username': user.username,
                    'full_name': user.full_name,
                    'email': user.email,
                    'role': user.role,
                    'is_admin': user.is_admin
                }
            })
        
        return jsonify({
            'success': False,
            'message': 'Sai tên đăng nhập hoặc mật khẩu'
        }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('username', None)
    return jsonify({'success': True})

@app.route('/api/statistics', methods=['GET'])
def api_get_statistics():
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Chưa đăng nhập'}), 401
        
        user = User.query.filter_by(username=session['username']).first()
        search_user = request.args.get('search_user', '', type=str)
        
        # Xây dựng query cơ bản
        query = SalesData.query
        
        # Xử lý tìm kiếm theo tài khoản quản lý - giống report
        if search_user:
            if User.query.filter_by(username=search_user, role='manager').first():
                manager = User.query.filter_by(username=search_user).first()
                subordinate_usernames = [u.username for u in manager.subordinates]
                query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
            else:
                query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
        elif not user.is_admin:
            if user.is_manager:
                subordinate_usernames = [u.username for u in user.subordinates]
                query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
            else:
                query = query.filter(SalesData.tai_khoan_quan_ly == user.username)
        
        # Tính toán thống kê
        total_money = query.with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
        total_paid = query.filter_by(trang_thai='Đã thanh toán').with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
        total_unpaid = query.filter_by(trang_thai='Chưa thanh toán').with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
        
        # Đếm số lượng hóa đơn
        total_invoices = query.count()
        total_paid_invoices = query.filter_by(trang_thai='Đã thanh toán').count()
        total_unpaid_invoices = query.filter_by(trang_thai='Chưa thanh toán').count()
        
        # Thống kê theo mã lộ
        ma_lo_stats = {}
        for record in query.all():
            if record.ma_lo not in ma_lo_stats:
                ma_lo_stats[record.ma_lo] = {
                    'total': 0,
                    'paid': 0,
                    'count': 0
                }
            ma_lo_stats[record.ma_lo]['total'] += record.tong_tien
            ma_lo_stats[record.ma_lo]['count'] += 1
            if record.trang_thai == 'Đã thanh toán':
                ma_lo_stats[record.ma_lo]['paid'] += record.tong_tien
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_money': total_money,
                'total_paid': total_paid,
                'total_unpaid': total_unpaid,
                'total_invoices': total_invoices,
                'total_paid_invoices': total_paid_invoices,
                'total_unpaid_invoices': total_unpaid_invoices,
                'ma_lo_stats': ma_lo_stats
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/data/view', methods=['GET'])
def api_view_data():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        # Lấy thông tin user hiện tại
        user = User.query.filter_by(username=session['username']).first()
        # Lấy các tham số tìm kiếm từ query string
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_user = request.args.get('search_user', '', type=str)
        search_ma_lo = request.args.get('search_ma_lo', '', type=str)
        search_trang_thai = request.args.get('search_trang_thai', '', type=str)  
        search_ten_khach_hang = request.args.get('search_ten_khach_hang', '', type=str).strip()
        search_ngay_thu = request.args.get('search_ngay_thu', '', type=str)
        # Xây dựng query cơ bản
        query = SalesData.query
        # Xử lý tìm kiếm theo tài khoản quản lý
        if search_user:
            if User.query.filter_by(username=search_user, role='manager').first():
                # Nếu tìm theo manager, chỉ lấy dữ liệu của users dưới quyền
                manager = User.query.filter_by(username=search_user).first()
                subordinate_usernames = [u.username for u in manager.subordinates]
                query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
            else:
                # Nếu tìm theo user thường
                query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
        elif not user.is_admin:  # Nếu không có tìm kiếm và không phải admin
            if user.is_manager:
                # Manager sẽ thấy dữ liệu của các user dưới quyền
                subordinate_usernames = [u.username for u in user.subordinates]
                query = query.filter(SalesData.tai_khoan_quan_ly.in_(subordinate_usernames))
            else:
                # User thường chỉ thấy dữ liệu của mình
                query = query.filter(SalesData.tai_khoan_quan_ly == user.username)
        # Áp dụng các điều kiện tìm kiếm khác
        if search_ma_lo:
            query = query.filter(SalesData.ma_lo.like(f'%{search_ma_lo}%'))

        if search_trang_thai:
            query = query.filter(SalesData.trang_thai == search_trang_thai)

        if search_ten_khach_hang:
            search_pattern = '%'.join(search_ten_khach_hang)
            query = query.filter(SalesData.ten_khach_hang.ilike(f'%{search_pattern}%'))

        if search_ngay_thu:
            try:
                search_date = datetime.strptime(search_ngay_thu, '%Y-%m-%d').date()
                query = query.filter(
                    and_(
                        SalesData.ngay_thu >= search_date,
                        SalesData.ngay_thu < search_date + timedelta(days=1)
                    )
                )
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400

        # Thực hiện phân trang
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Tính toán thống kê
        total_amount = query.with_entities(func.sum(SalesData.tong_tien)).scalar() or 0
        total_invoices = query.count()

        # Format dữ liệu trả về
        data = [{
            'id': item.id,
            'stt': item.stt,
            'ma_lo': item.ma_lo,
            'tt_hd': item.tt_hd,
            'ma_khach_hang': item.ma_khach_hang,
            'ten_khach_hang': item.ten_khach_hang,
            'dia_chi': item.dia_chi,
            'so_dien_thoai': getattr(item, 'so_dien_thoai', ''),
            'kwh': item.kwh,
            'tien_dien': item.tien_dien,
            'vat': item.vat,
            'tong_tien': item.tong_tien,
            'tai_khoan_quan_ly': item.tai_khoan_quan_ly,
            'trang_thai': item.trang_thai,
            'ngay_thu': item.ngay_thu.strftime('%Y-%m-%d %H:%M:%S') if item.ngay_thu else None
        } for item in pagination.items]
        # Lấy danh sách mã lộ cho filter
        if user.is_admin:
            if search_user:
                selected_user = User.query.filter_by(username=search_user).first()
                if selected_user:
                    if selected_user.role == 'manager':
                        subordinate_usernames = [u.username for u in selected_user.subordinates]
                        ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                            SalesData.tai_khoan_quan_ly.in_(subordinate_usernames)
                        )
                    else:
                        ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                            SalesData.tai_khoan_quan_ly == search_user
                        )
            else:
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct()
        elif user.is_manager:
            subordinate_usernames = [u.username for u in user.subordinates]
            if search_user and search_user in subordinate_usernames:
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                    SalesData.tai_khoan_quan_ly == search_user
                )
            else:
                ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                    SalesData.tai_khoan_quan_ly.in_(subordinate_usernames)
                )
        else:
            ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(
                SalesData.tai_khoan_quan_ly == user.username
            )
        ma_lo_list = [item[0] for item in ma_lo_query.all()]
        # Chuẩn bị danh sách users có cấu trúc phân cấp
        if user.is_admin:
            # Lấy tất cả managers
            managers = User.query.filter_by(role='manager').all()
            users_list = [] 
            # Thêm managers và users của họ
            for manager in managers:
                users_list.append({
                    'username': manager.username,
                    'role': 'manager',
                    'manager_username': None
                })
                
                for sub_user in manager.subordinates:
                    users_list.append({
                        'username': sub_user.username,
                        'role': 'user',
                        'manager_username': manager.username
                    })   
            # Thêm users không có manager
            independent_users = User.query.filter(
                User.role == 'user',
                User.manager_id.is_(None)
            ).all()
            for ind_user in independent_users:
                users_list.append({
                    'username': ind_user.username,
                    'role': 'user',
                    'manager_username': None
                })
                
        elif user.is_manager:
            users_list = [{
                'username': user.username,
                'role': 'manager',
                'manager_username': None
            }]
            
            users_list.extend([{
                'username': sub_user.username,
                'role': 'user',
                'manager_username': user.username
            } for sub_user in user.subordinates])
        else:
            users_list = [{
                'username': user.username,
                'role': 'user',
                'manager_username': None
            }]

        return jsonify({
            'success': True,
            'data': {
                'items': data,
                'pagination': {
                    'current_page': pagination.page,
                    'total_pages': pagination.pages,
                    'per_page': per_page,
                    'total_items': pagination.total
                },
                'summary': {
                    'total_amount': total_amount,
                    'total_invoices': total_invoices
                },
                'filters': {
                    'ma_lo_list': ma_lo_list,
                    'trang_thai_list': ['Đã thanh toán', 'Chưa thanh toán']
                },
                'users': users_list
            }
        })

    except Exception as e:
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500
    
@app.route('/api/invoice/check-payment-status/<int:invoice_id>', methods=['GET'])
def check_payment_status(invoice_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Lấy thông tin user hiện tại
        user = User.query.filter_by(username=session['username']).first()
        
        # Tìm hóa đơn
        invoice = SalesData.query.get_or_404(invoice_id)
        
        # Kiểm tra quyền truy cập
        if not user.is_admin and invoice.tai_khoan_quan_ly != user.username:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        return jsonify({
            'success': True,
            'data': {
                'invoice_id': invoice.id,
                'ma_khach_hang': invoice.ma_khach_hang,
                'ten_khach_hang': invoice.ten_khach_hang,
                'trang_thai': invoice.trang_thai,
                'ngay_thu': invoice.ngay_thu.strftime('%Y-%m-%d %H:%M:%S') if invoice.ngay_thu else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True)