"""
Script migration để thêm cột so_dien_thoai vào bảng sales_data
Chạy script này để cập nhật database mà không làm mất dữ liệu cũ
"""
import sqlite3
import os

# Đường dẫn đến database
db_path = 'instance/users.db'

if not os.path.exists(db_path):
    print(f"❌ Không tìm thấy database tại: {db_path}")
    print("Vui lòng chạy app.py trước để tạo database")
    exit(1)

try:
    # Kết nối đến database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Kiểm tra xem cột đã tồn tại chưa
    cursor.execute("PRAGMA table_info(sales_data)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'so_dien_thoai' in columns:
        print("✅ Cột 'so_dien_thoai' đã tồn tại trong database")
    else:
        # Thêm cột mới
        cursor.execute("ALTER TABLE sales_data ADD COLUMN so_dien_thoai VARCHAR(20)")
        conn.commit()
        print("✅ Đã thêm cột 'so_dien_thoai' vào bảng sales_data thành công!")
    
    # Kiểm tra lại
    cursor.execute("PRAGMA table_info(sales_data)")
    print("\n📋 Cấu trúc bảng sales_data hiện tại:")
    for column in cursor.fetchall():
        print(f"  - {column[1]} ({column[2]})")
    
    conn.close()
    print("\n✅ Migration hoàn tất!")
    
except sqlite3.Error as e:
    print(f"❌ Lỗi khi thực hiện migration: {e}")
except Exception as e:
    print(f"❌ Lỗi không xác định: {e}")
