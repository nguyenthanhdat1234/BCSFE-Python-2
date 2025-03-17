import os
import tempfile
from flask import Flask, request, jsonify
import sys
from flask_cors import CORS

# Thêm đường dẫn để tìm BCSFE_Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'BCSFE-Python')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'BCSFE-Python', 'src')))

try:
    # Import các module cần thiết
    from BCSFE_Python import helper, parse_save, server_handler
    print("Tất cả các import thành công!")
except ImportError as e:
    print(f"Lỗi khi import BCSFE_Python: {e}")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Thiết lập CORS để chỉ cho phép các domain được chấp nhận
ALLOWED_ORIGINS = [
    'http://example.com',
    'https://example.com',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'https://bcsfe-web-app.onrender.com'
]

# Áp dụng CORS với các domain được chỉ định
CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Middleware để kiểm tra origin
@app.before_request
def check_origin():
    origin = request.headers.get('Origin')
    if not origin:
        return None
    
    if origin not in ALLOWED_ORIGINS:
        return jsonify({
            'status': 'error', 
            'message': 'Origin không được phép truy cập'
        }), 403
    
    return None

# Thư mục để lưu trữ file tạm thời
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'bcsfe_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/api/auto_transfer', methods=['POST'])
def auto_transfer():
    """Tự động tải xuống từ mã hiện tại, chỉnh sửa và tạo mã mới"""
    try:
        # Lấy dữ liệu đầu vào
        transfer_code = request.form.get('transfer_code', '')
        confirmation_code = request.form.get('confirmation_code', '')
        country_code = request.form.get('country_code', 'en')
        game_version = request.form.get('game_version', '11.3.0')
        cat_food = request.form.get('cat_food', None)
        
        # Kiểm tra đầu vào
        if not transfer_code or not confirmation_code:
            return jsonify({'status': 'error', 'message': 'Mã chuyển giao và mã xác nhận là bắt buộc'})
        
        # Kiểm tra định dạng mã
        transfer_code = helper.check_hex(transfer_code.lower().replace("o", "0"))
        confirmation_code = helper.check_dec(confirmation_code.lower().replace("o", "0"))
        
        if not transfer_code or not confirmation_code:
            return jsonify({'status': 'error', 'message': 'Định dạng mã không đúng'})
        
        # Bước 1: Tải xuống từ mã hiện tại
        numeric_game_version = helper.str_to_gv(game_version)
        response = server_handler.download_save(
            country_code, transfer_code, confirmation_code, numeric_game_version
        )
        
        save_data = response.content
        if not server_handler.test_is_save_data(save_data):
            return jsonify({'status': 'error', 'message': 'Mã chuyển giao/xác nhận không đúng hoặc không tìm thấy dữ liệu'})
        
        # Lưu file tạm thời
        download_path = os.path.join(app.config['UPLOAD_FOLDER'], f'auto_save_{transfer_code}')
        helper.write_file_bytes(download_path, save_data)
        
        # Phân tích file save
        save_stats = parse_save.start_parse(save_data, country_code)
        headers = response.headers
        save_stats['token'] = headers.get('nyanko-password-refresh-token', '')
        
        # Bước 2: Chỉnh sửa dữ liệu (ví dụ: Cat Food)
        original_values = {
            'cat_food': save_stats['cat_food']['Value'],
            'xp': save_stats['xp']['Value'],
            'rare_tickets': save_stats['rare_tickets']['Value'],
            'platinum_tickets': save_stats['platinum_tickets']['Value']
        }
        
        if cat_food is not None:
            save_stats['cat_food']['Value'] = int(cat_food)
        
        # Bước 3: Tải lên để lấy mã mới
        upload_data = server_handler.upload_handler(save_stats, download_path)
        if upload_data is None:
            return jsonify({'status': 'error', 'message': 'Không thể tải lên máy chủ'})
        
        upload_data, save_stats = upload_data
        if upload_data is None or 'transferCode' not in upload_data:
            return jsonify({'status': 'error', 'message': 'Không nhận được mã chuyển giao mới'})
        
        # Trả về kết quả
        result = {
            'status': 'success',
            'message': 'Đã tạo mã chuyển giao mới thành công',
            'old_transfer_code': transfer_code,
            'old_confirmation_code': confirmation_code,
            'new_transfer_code': upload_data['transferCode'],
            'new_confirmation_code': upload_data['pin'],
            'original_values': original_values,
            'modified_values': {
                'cat_food': save_stats['cat_food']['Value'],
                'xp': save_stats['xp']['Value'],
                'rare_tickets': save_stats['rare_tickets']['Value'],
                'platinum_tickets': save_stats['platinum_tickets']['Value']
            },
            'inquiry_code': save_stats['inquiry_code']
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi khi xử lý: {str(e)}'})

@app.route('/')
def index():
    """Trang chủ đơn giản"""
    return "API Auto Transfer hoạt động bình thường. Sử dụng /api/auto_transfer với phương thức POST."

@app.route('/test')
def test():
    """API kiểm tra"""
    try:
        return jsonify({
            'status': 'success',
            'message': 'Hệ thống hoạt động bình thường',
            'import_status': 'Đã import BCSFE_Python thành công',
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER'])
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True)