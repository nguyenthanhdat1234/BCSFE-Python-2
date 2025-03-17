import os
import base64
import json
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import sys
import importlib.util
from flask_cors import CORS

# Bước debug: In ra đường dẫn hiện tại và các đường dẫn trong sys.path
print(f"Đường dẫn hiện tại: {os.path.abspath(os.path.dirname(__file__))}")
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'BCSFE-Python', 'src'))
print(f"Đường dẫn src: {src_path}")

# Kiểm tra xem thư mục src có tồn tại không
if os.path.exists(src_path):
    print(f"Thư mục src tồn tại, thêm vào sys.path")
    sys.path.insert(0, src_path)
else:
    print(f"CẢNH BÁO: Thư mục src không tồn tại!")

# In ra tất cả các đường dẫn trong sys.path để kiểm tra
print("Python sys.path:")
for p in sys.path:
    print(f"  - {p}")

# Thử import để xem lỗi chi tiết
try:
    from BCSFE_Python import helper
    print("Import BCSFE_Python thành công!")
except ImportError as e:
    print(f"Lỗi khi import BCSFE_Python: {e}")
    
    # Thử tìm module trực tiếp
    bcsfe_paths = []
    for root, dirs, files in os.walk(os.path.abspath(os.path.dirname(__file__))):
        if '__init__.py' in files and os.path.basename(root) in ['BCSFE_Python', 'BCSFE-Python']:
            bcsfe_paths.append(root)
    
    if bcsfe_paths:
        print(f"Tìm thấy các thư mục BCSFE_Python tại:")
        for path in bcsfe_paths:
            print(f"  - {path}")
            sys.path.insert(0, os.path.dirname(path))
    else:
        print("Không tìm thấy thư mục BCSFE_Python nào chứa __init__.py")

# Thử import lại sau khi đã thêm các đường dẫn mới
try:
    # Import các module cần thiết từ BCSFE_Python
    from BCSFE_Python import helper, parse_save, patcher, serialise_save
    from BCSFE_Python import server_handler, user_input_handler, config_manager
    from BCSFE_Python.edits.basic import basic_items
    from BCSFE_Python.edits.cats import get_remove_cats, upgrade_cats, evolve_cats
    from BCSFE_Python.edits.levels import clear_tutorial
    
    print("Tất cả các import thành công!")
except ImportError as e:
    print(f"Vẫn còn lỗi sau khi thử các cách khác nhau: {e}")
    print("Ứng dụng sẽ không chạy được. Hãy cài đặt BCSFE_Python đúng cách.")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Thiết lập CORS để chỉ cho phép các domain được chấp nhận
ALLOWED_ORIGINS = [
    'http://example.com',  # Thay domain này bằng domain của bạn
    'https://example.com',
    'http://localhost:5000',
    'http://127.0.0.1:5000'
]

# Áp dụng CORS với các domain được chỉ định
CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Middleware để kiểm tra origin trước khi xử lý request
@app.before_request
def check_origin():
    # Lấy origin từ header
    origin = request.headers.get('Origin')
    
    # Bỏ qua kiểm tra đối với yêu cầu từ cùng nguồn (không có header Origin)
    if not origin:
        return None
    
    # Nếu origin không nằm trong danh sách được phép, từ chối yêu cầu
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Lưu trữ dữ liệu phiên làm việc
session_data = {}

def allowed_file(filename):
    """Kiểm tra xem file có được phép tải lên không"""
    return True  # Cho phép tất cả các file vì chúng ta đang xử lý file save game cụ thể

@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Xử lý tải lên file save"""
    if 'file' not in request.files:
        flash('Không tìm thấy phần file')
        return redirect(request.url)
    file = request.files['file']
    
    if file.filename == '':
        flash('Chưa chọn file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        # Phân tích file save
        try:
            save_data = helper.read_file_bytes(save_path)
            country_code = patcher.detect_game_version(save_data)
            if not country_code:
                country_code = request.form.get('country_code', 'en')
            
            save_stats = parse_save.start_parse(save_data, country_code)
            
            # Lưu dữ liệu vào session
            session_id = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')
            session_data[session_id] = {
                'save_path': save_path,
                'save_stats': save_stats,
                'country_code': country_code
            }
            
            # Trích xuất một số thông tin cơ bản để hiển thị
            basic_info = {
                'inquiry_code': save_stats['inquiry_code'],
                'cat_food': save_stats['cat_food']['Value'],
                'xp': save_stats['xp']['Value'],
                'rare_tickets': save_stats['rare_tickets']['Value'],
                'platinum_tickets': save_stats['platinum_tickets']['Value'],
                'user_rank': helper.calculate_user_rank(save_stats)
            }
            
            return render_template('editor.html', session_id=session_id, basic_info=basic_info)
        except Exception as e:
            flash(f'Lỗi khi phân tích file save: {str(e)}')
            return redirect(url_for('index'))
    
    flash('Loại file không được hỗ trợ')
    return redirect(url_for('index'))

@app.route('/download/<session_id>', methods=['GET'])
def download_save(session_id):
    """Tải xuống file save đã chỉnh sửa"""
    if session_id not in session_data:
        flash('Phiên làm việc không hợp lệ hoặc đã hết hạn')
        return redirect(url_for('index'))
    
    try:
        session_info = session_data[session_id]
        save_stats = session_info['save_stats']
        country_code = session_info['country_code']
        
        # Tạo file save mới
        save_data = serialise_save.start_serialize(save_stats)
        save_data = patcher.patch_save_data(save_data, country_code)
        
        # Lưu file tạm thời trước khi tải xuống
        download_path = os.path.join(app.config['UPLOAD_FOLDER'], f'SAVE_DATA_{session_id}')
        helper.write_file_bytes(download_path, save_data)
        
        return send_file(download_path, as_attachment=True, download_name='SAVE_DATA')
    except Exception as e:
        flash(f'Lỗi khi tạo file save: {str(e)}')
        return redirect(url_for('index'))

@app.route('/edit/<action>/<session_id>', methods=['POST'])
def edit_save(action, session_id):
    """Xử lý các hành động chỉnh sửa"""
    if session_id not in session_data:
        return jsonify({'status': 'error', 'message': 'Phiên làm việc không hợp lệ hoặc đã hết hạn'})
    
    session_info = session_data[session_id]
    save_stats = session_info['save_stats']
    
    try:
        # Xử lý các hành động chỉnh sửa khác nhau
        if action == 'cat_food':
            value = int(request.form.get('value', 0))
            save_stats['cat_food']['Value'] = value
            return jsonify({'status': 'success', 'message': f'Đã cập nhật Cat Food thành {value}'})
        
        elif action == 'xp':
            value = int(request.form.get('value', 0))
            save_stats['xp']['Value'] = value
            return jsonify({'status': 'success', 'message': f'Đã cập nhật XP thành {value}'})
        
        elif action == 'rare_tickets':
            value = int(request.form.get('value', 0))
            save_stats['rare_tickets']['Value'] = value
            return jsonify({'status': 'success', 'message': f'Đã cập nhật Rare Tickets thành {value}'})
        
        elif action == 'platinum_tickets':
            value = int(request.form.get('value', 0))
            save_stats['platinum_tickets']['Value'] = value
            return jsonify({'status': 'success', 'message': f'Đã cập nhật Platinum Tickets thành {value}'})
        
        elif action == 'get_cats':
            # Thêm mèo theo ID
            cat_ids = [int(x) for x in request.form.get('cat_ids', '').split(',') if x.strip()]
            if cat_ids:
                save_stats = get_remove_cats.get_cat_ids(save_stats, 1, "thêm", cat_ids)
                return jsonify({'status': 'success', 'message': f'Đã thêm {len(cat_ids)} mèo'})
            return jsonify({'status': 'error', 'message': 'Không có ID mèo nào được chọn'})
        
        elif action == 'upgrade_cats':
            # Nâng cấp mèo
            cat_ids = [int(x) for x in request.form.get('cat_ids', '').split(',') if x.strip()]
            base_level = int(request.form.get('base_level', 30))
            plus_level = int(request.form.get('plus_level', 0))
            
            if cat_ids:
                # Chuẩn bị dữ liệu nâng cấp
                save_stats['cat_upgrades'] = upgrade_cats.upgrade_handler(
                    data=save_stats['cat_upgrades'],
                    ids=cat_ids,
                    item_name="cat",
                    save_stats=save_stats
                )
                save_stats = upgrade_cats.set_user_popups(save_stats)
                return jsonify({'status': 'success', 'message': f'Đã nâng cấp {len(cat_ids)} mèo lên cấp {base_level}+{plus_level}'})
            return jsonify({'status': 'error', 'message': 'Không có ID mèo nào được chọn'})
        
        elif action == 'evolve_cats':
            # Tiến hóa mèo
            cat_ids = [int(x) for x in request.form.get('cat_ids', '').split(',') if x.strip()]
            if cat_ids:
                save_stats = evolve_cats.evolve_handler_ids(
                    save_stats=save_stats,
                    val=2,  # 2 = True Form
                    string="set",
                    ids=cat_ids,
                    forced=True
                )
                return jsonify({'status': 'success', 'message': f'Đã tiến hóa {len(cat_ids)} mèo'})
            return jsonify({'status': 'error', 'message': 'Không có ID mèo nào được chọn'})
        
        elif action == 'clear_tutorial':
            # Hoàn thành hướng dẫn
            save_stats = clear_tutorial.clear_tutorial(save_stats)
            return jsonify({'status': 'success', 'message': 'Đã hoàn thành hướng dẫn'})
        
        elif action == 'upload_save':
            try:
                # Tải lên máy chủ để lấy mã chuyển giao
                upload_data = server_handler.upload_handler(save_stats, session_info['save_path'])
                if upload_data is None:
                    return jsonify({'status': 'error', 'message': 'Không thể tải lên máy chủ'})
                
                upload_data, save_stats = upload_data
                if upload_data is None:
                    return jsonify({'status': 'error', 'message': 'Không thể tải lên máy chủ'})
                
                if 'transferCode' not in upload_data:
                    return jsonify({'status': 'error', 'message': 'Không nhận được mã chuyển giao'})
                
                return jsonify({
                    'status': 'success', 
                    'message': 'Đã tải lên máy chủ thành công',
                    'transfer_code': upload_data['transferCode'],
                    'confirmation_code': upload_data['pin']
                })
            except Exception as e:
                return jsonify({'status': 'error', 'message': f'Lỗi khi tải lên máy chủ: {str(e)}'})
        
        else:
            return jsonify({'status': 'error', 'message': f'Hành động không được hỗ trợ: {action}'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi khi chỉnh sửa: {str(e)}'})

@app.route('/download_from_codes', methods=['POST'])
def download_from_codes():
    """Tải về file save từ mã chuyển giao và mã xác nhận"""
    try:
        transfer_code = request.form.get('transfer_code', '')
        confirmation_code = request.form.get('confirmation_code', '')
        country_code = request.form.get('country_code', 'en')
        game_version = request.form.get('game_version', '11.3.0')
        
        if not transfer_code or not confirmation_code:
            flash('Mã chuyển giao và mã xác nhận là bắt buộc')
            return redirect(url_for('index'))
        
        # Kiểm tra định dạng mã
        transfer_code = helper.check_hex(transfer_code.lower().replace("o", "0"))
        confirmation_code = helper.check_dec(confirmation_code.lower().replace("o", "0"))
        
        if not transfer_code or not confirmation_code:
            flash('Định dạng mã không đúng')
            return redirect(url_for('index'))
        
        # Tải file save
        numeric_game_version = helper.str_to_gv(game_version)
        response = server_handler.download_save(
            country_code, transfer_code, confirmation_code, numeric_game_version
        )
        
        save_data = response.content
        if not server_handler.test_is_save_data(save_data):
            flash('Mã chuyển giao/xác nhận không đúng hoặc không tìm thấy dữ liệu')
            return redirect(url_for('index'))
        
        # Lưu file tạm thời
        download_path = os.path.join(app.config['UPLOAD_FOLDER'], 'downloaded_SAVE_DATA')
        helper.write_file_bytes(download_path, save_data)
        
        # Phân tích file save để tạo phiên làm việc mới
        save_stats = parse_save.start_parse(save_data, country_code)
        headers = response.headers
        save_stats['token'] = headers.get('nyanko-password-refresh-token', '')
        
        # Tạo session mới
        session_id = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')
        session_data[session_id] = {
            'save_path': download_path,
            'save_stats': save_stats,
            'country_code': country_code
        }
        
        # Trích xuất thông tin cơ bản
        basic_info = {
            'inquiry_code': save_stats['inquiry_code'],
            'cat_food': save_stats['cat_food']['Value'],
            'xp': save_stats['xp']['Value'],
            'rare_tickets': save_stats['rare_tickets']['Value'],
            'platinum_tickets': save_stats['platinum_tickets']['Value'],
            'user_rank': helper.calculate_user_rank(save_stats)
        }
        
        # Chuyển hướng đến trình chỉnh sửa
        flash('Đã tải dữ liệu save thành công')
        return render_template('editor.html', session_id=session_id, basic_info=basic_info)
        
    except Exception as e:
        flash(f'Lỗi khi tải dữ liệu save: {str(e)}')
        return redirect(url_for('index'))

@app.route('/api/auto_transfer', methods=['POST'])
def auto_transfer():
    """Tự động tải xuống từ mã hiện tại, chỉnh sửa và tạo mã mới"""
    try:
        # Lấy dữ liệu đầu vào
        transfer_code = request.form.get('transfer_code', '')
        confirmation_code = request.form.get('confirmation_code', '')
        country_code = request.form.get('country_code', 'en')
        game_version = request.form.get('game_version', '11.3.0')
        cat_food = request.form.get('cat_food', None)  # Có thể thêm các tham số chỉnh sửa khác
        
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

if __name__ == '__main__':
    app.run(debug=True)