from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from datetime import datetime, timedelta
from io import BytesIO
from flask import Response
import openpyxl
from unidecode import unidecode
from sqlalchemy import and_, func
from sqlalchemy import event
from sqlalchemy import or_

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
# Cấu hình upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Tạo thư mục uploads nếu chưa có
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Model để lưu dữ liệu
class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stt = db.Column(db.Integer)
    ma_lo = db.Column(db.String(20))
    tt_hd = db.Column(db.String(20))
    ma_khach_hang = db.Column(db.String(50))
    ten_khach_hang = db.Column(db.String(100), index=True)
    dia_chi = db.Column(db.String(200))
    kwh = db.Column(db.String(50))
    tien_dien = db.Column(db.Float)
    vat = db.Column(db.Float)
    tong_tien = db.Column(db.Float)
    tai_khoan_quan_ly = db.Column(db.String(80))  # Thêm trường này
    trang_thai = db.Column(db.String(50))
    ngay_thu = db.Column(db.DateTime, nullable=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Thêm trường is_admin
    is_active = db.Column(db.Boolean, default=True)  # Thêm trường để khóa/mở khóa tài khoản

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def init_db():
    with app.app_context():
        # Tạo function unidecode cho SQLite
        def sqlite_unidecode(string):
            return unidecode(string) if string else None
        
        # Đăng ký function với SQLite
        engine = db.get_engine()
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



@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
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
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Thêm người dùng vào cơ sở dữ liệu
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')


# Thêm các route mới cho admin
@app.route('/admin')
@admin_required
def admin_dashboard():
    users = User.query.all()
    return render_template('admin/dashboard.html', users=users)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        email = request.form['email']
        is_admin = 'is_admin' in request.form
        is_active = 'is_active' in request.form
        new_password = request.form['new_password']

        if email != user.email:
            if User.query.filter_by(email=email).first():
                flash('Email already exists')
                return redirect(url_for('admin_edit_user', user_id=user_id))
            user.email = email

        if new_password:
            user.set_password(new_password)

        user.is_admin = is_admin
        user.is_active = is_active
        
        db.session.commit()
        flash('User updated successfully')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/edit_user.html', user=user)

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
                return redirect(url_for('dashboard'))
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    return render_template('admin/dashboard.html', user=user)

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

@app.route('/admin/import', methods=['GET', 'POST'])
@admin_required
def import_data():
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
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                df = pd.read_excel(filepath)
                
                for index, row in df.iterrows():
                    existing_data = SalesData.query.filter_by(ma_khach_hang=row['Mã Khách hàng']).first()
                    
                    if existing_data:
                        flash(f"Customer with 'Mã Khách hàng' {row['Mã Khách hàng']} already exists.")
                        return redirect(url_for('import_data'))
                    
                    # Gán giá trị mặc định cho 'trang_thai'
                    trang_thai = 'Chưa thanh toán'  # Giá trị mặc định nếu không có trong file Excel
                    
                    data = SalesData(
                        stt=row['STT'],
                        ma_lo=row['Mã lộ'],
                        tt_hd=row['TT HĐ'],
                        ma_khach_hang=row['Mã Khách hàng'],
                        ten_khach_hang=row['Tên Khách hàng'],
                        dia_chi=row['Địa chỉ'],
                        kwh=row['Kwh'],
                        tien_dien=float(row['Tiền điện']),
                        vat=float(row['VAT']),
                        tong_tien=float(row['Tổng tiền']),
                        tai_khoan_quan_ly=selected_user,
                        trang_thai=trang_thai  # Gán giá trị vào cột 'trang_thai'
                    )
                    db.session.add(data)
                db.session.commit()
                flash('Data imported successfully')
                os.remove(filepath)
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error importing data: {str(e)}')
                
            return redirect(url_for('view_data'))
    
    users = User.query.filter_by(is_admin=False).all()  # Lấy danh sách user không phải admin
    return render_template('admin/import.html', users=users)

    
    users = User.query.filter_by(is_admin=False).all()  # Lấy danh sách user không phải admin
    return render_template('admin/import.html', users=users)



@app.route('/export', methods=['GET'])
def export_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    
    if user.is_admin:
        query = SalesData.query
    else:
        query = SalesData.query.filter_by(tai_khoan_quan_ly=user.username)
    
    # Lấy toàn bộ dữ liệu cần xuất
    data = query.all()

    # Tạo một workbook mới
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Data"

    # Viết tiêu đề cột
    ws.append(['STT', 'Mã Lộ', 'Mã Khách Hàng', 'Tên Khách Hàng', 'Địa Chỉ', 'Tổng Tiền', 'Tài Khoản Quản Lý', 'Trạng Thái', 'Ngày thu'])

    # Viết dữ liệu vào các hàng trong Excel
    for row in data:
        ws.append([row.stt, row.ma_lo, row.ma_khach_hang, row.ten_khach_hang, row.dia_chi, row.tong_tien, row.tai_khoan_quan_ly, row.trang_thai, row.ngay_thu])

    # Lưu workbook vào một bộ nhớ (BytesIO) để gửi qua Response
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Trả về dữ liệu dưới dạng file Excel
    return Response(output.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={
        'Content-Disposition': 'attachment; filename=sales_data.xlsx'
    })

@app.route('/data', methods=['GET', 'POST'])
def view_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_user = request.args.get('search_user', '', type=str)
    search_ma_lo = request.args.get('search_ma_lo', '', type=str)
    search_trang_thai = request.args.get('search_trang_thai', '', type=str)
    search_ten_khach_hang = request.args.get('search_ten_khach_hang', '', type=str)
    search_ngay_thu = request.args.get('search_ngay_thu', '', type=str)
    
    user = User.query.filter_by(username=session['username']).first()
    
    if request.method == 'POST':
        if not user.is_admin:
            abort(403)
            
        selected_ids = request.form.getlist('selected_ids')
        try:
            for record_id in selected_ids:
                record = SalesData.query.get(record_id)
                if record:
                    db.session.delete(record)
            db.session.commit()
            flash('Selected records have been deleted successfully.')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting records: {str(e)}', 'error')
        return redirect(url_for('view_data', page=page, per_page=per_page))
    
    if user.is_admin:
        query = SalesData.query
    else:
        query = SalesData.query.filter_by(tai_khoan_quan_ly=user.username)
    
    if search_user:
        query = query.filter(SalesData.tai_khoan_quan_ly == search_user)
    
    if search_ma_lo:
        query = query.filter(SalesData.ma_lo.like(f'%{search_ma_lo}%'))

    if search_trang_thai:
        query = query.filter(SalesData.trang_thai == search_trang_thai)


    if search_ten_khach_hang:
        query = query.filter(SalesData.ten_khach_hang.ilike(f'%{search_ten_khach_hang}%'))

    if search_ngay_thu:
        try:
            # Chuyển đổi chuỗi ngày thành đối tượng datetime
            search_ngay_thu_date = datetime.strptime(search_ngay_thu, '%Y-%m-%d').date()
            # Lọc theo ngày (bỏ phần giờ)
            query = query.filter(SalesData.ngay_thu >= search_ngay_thu_date)
            query = query.filter(SalesData.ngay_thu < search_ngay_thu_date + timedelta(days=1))
        except ValueError:
            # Nếu ngày không hợp lệ, không lọc theo ngày thu
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
    try:
        # Phân trang dữ liệu
        data = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Tính tổng tiền
        total_amount = query.with_entities(db.func.sum(SalesData.tong_tien)).scalar() or 0
        
        # Tính tổng số hóa đơn
        total_invoices = query.count()  # Đếm số bản ghi
        
        # Lấy danh sách users
        users = User.query.filter_by(is_admin=False).all()
        
        # Lấy danh sách mã lộ
        if user.is_admin:
            ma_lo_query = db.session.query(SalesData.ma_lo).distinct()
            if search_user:
                ma_lo_query = ma_lo_query.filter(SalesData.tai_khoan_quan_ly == search_user)
        else:
            ma_lo_query = db.session.query(SalesData.ma_lo).distinct().filter(SalesData.tai_khoan_quan_ly == user.username)
        
        ma_lo_list = [item[0] for item in ma_lo_query.all()]
        
        return render_template('admin/view_data.html', data=data, per_page=per_page, user=user, users=users, 
                               search_user=search_user, search_ma_lo=search_ma_lo, ma_lo_list=ma_lo_list,
                               search_trang_thai=search_trang_thai, search_ten_khach_hang=search_ten_khach_hang, search_ngay_thu=search_ngay_thu, total_amount=total_amount,
                               total_invoices=total_invoices)  # Truyền thêm tổng số hóa đơn
    except Exception as e:
        flash(f'Error loading data: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/report', methods=['GET'])
def report():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    search_user = request.args.get('search_user', '', type=str)
    
    query = SalesData.query
    
    if current_user.is_admin:
        if search_user:
            query = query.filter_by(tai_khoan_quan_ly=search_user)
        users = User.query.filter_by(is_admin=False).all()
    else:
        query = query.filter_by(tai_khoan_quan_ly=current_user.username)
        users = []
        search_user = current_user.username

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
            daily_stats[date_str]['paid'] += record.tong_tien
            daily_stats[date_str]['count'] += 1

    # Sắp xếp theo ngày và lấy 7 ngày gần nhất
    chart_dates = sorted(daily_stats.keys(), reverse=True)[:7]
    chart_dates.reverse()  # Đảo ngược lại để hiển thị theo thứ tự thời gian
    
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
                         total_money=total_money,
                         total_paid_money=total_paid_money,
                         total_unpaid_money=total_unpaid_money,
                         total_invoices=total_invoices,
                         total_paid_invoices=total_paid_invoices,
                         total_unpaid_invoices=total_unpaid_invoices,
                         users=users,
                         search_user=search_user,
                         is_admin=current_user.is_admin,
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
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin123')  # Đổi mật khẩu này sau khi tạo xong
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)