import os
import tempfile
from flask import Flask, request, jsonify, send_file
import sys
from flask_cors import CORS
import threading
import uuid
import time

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

# Tạo mutex cho các hoạt động truy cập file
file_mutex = threading.Lock()
result_mutex = threading.Lock()

# Thiết lập CORS để chỉ cho phép các domain được chấp nhận
ALLOWED_ORIGINS = [
    'http://example.com',
    'https://example.com',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'https://bcsfe-web-app.onrender.com',
    'http://localhost:54216'  # Thêm localhost của TheBattleCats
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

# API để tải xuống file save data
@app.route('/api/download_save_data/<security_code>', methods=['GET'])
def download_save_data(security_code):
    try:
        # Đường dẫn tới file save data đã chỉnh sửa
        modified_save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modified_save_file.sav')
        
        # Kiểm tra xem file có tồn tại không
        if not os.path.exists(modified_save_path):
            return jsonify({'status': 'error', 'message': 'Không tìm thấy file save data'}), 404
        
        # Sử dụng mutex để đảm bảo không có ai đang ghi vào file
        with file_mutex:
            # Tạo bản sao tạm thời của file để tránh conflict khi tải xuống
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'download_copy_{security_code}_{uuid.uuid4()}.sav')
            with open(modified_save_path, 'rb') as src_file:
                file_content = src_file.read()
                with open(temp_file_path, 'wb') as dest_file:
                    dest_file.write(file_content)
        
        # Gửi file đã sao chép
        response = send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f'{security_code}_SAVE_DATA.sav',
            mimetype='application/octet-stream'
        )
        
        # Thiết lập callback để xóa file tạm thời sau khi gửi
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                print(f"[WARNING] Không thể xóa file tạm thời: {str(e)}")
        
        return response
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Lỗi khi tải xuống file save data: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error', 
            'message': f'Lỗi khi tải file: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/auto_transfer', methods=['POST'])
def auto_transfer():
    # Tạo ID yêu cầu duy nhất
    request_id = str(uuid.uuid4())
    # Tạo đường dẫn file riêng cho yêu cầu này
    current_save_file = os.path.join(app.config['UPLOAD_FOLDER'], f'current_save_{request_id}.sav')
    modified_save_file = os.path.join(app.config['UPLOAD_FOLDER'], f'modified_save_{request_id}.sav')
    
    try:
        # Import cần thiết
        import datetime
        import json
        import requests
        
        # Lấy dữ liệu đầu vào
        transfer_code = request.form.get('transfer_code', '')
        confirmation_code = request.form.get('confirmation_code', '')
        country_code = request.form.get('country_code', 'en')
        game_version = request.form.get('game_version', '11.3.0')
        cat_food = request.form.get('cat_food', None)
        change_inquiry = request.form.get('change_inquiry', 'true').lower() == 'true'
        security_code = request.form.get('security_code', '1')  # Mặc định là 1
        
        print(f"[INFO] Bắt đầu auto_transfer với transfer_code={transfer_code}, confirmation_code={confirmation_code}, request_id={request_id}")
        
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
        
        # Sử dụng file riêng cho yêu cầu này
        helper.write_file_bytes(current_save_file, save_data)
        print(f"[INFO] Đã tải xuống và lưu file tại: {current_save_file}")
        
        # Phân tích file save
        save_stats = parse_save.start_parse(save_data, country_code)
        headers = response.headers
        save_stats['token'] = headers.get('nyanko-password-refresh-token', '')
        original_inquiry = save_stats['inquiry_code']
        print(f"[INFO] Original inquiry code: {original_inquiry}")
        
        # Bước 2: Chỉnh sửa dữ liệu (Cat Food) - Chọn 2 > 2 > y
        original_values = {
            'cat_food': save_stats['cat_food']['Value'],
            'xp': save_stats['xp']['Value'],
            'rare_tickets': save_stats['rare_tickets']['Value'],
            'platinum_tickets': save_stats['platinum_tickets']['Value']
        }
        
        # Xử lý cat food theo security code nếu không có giá trị cụ thể
        if cat_food is None:
            # Chọn giá trị cat food dựa trên security code
            if security_code == '1':
                cat_food = 19999
            elif security_code == '2':
                cat_food = 18000
            elif security_code == '3':
                cat_food = 2000
            else:
                cat_food = 19999  # Mặc định nếu không rõ security code
        
        save_stats['cat_food']['Value'] = int(cat_food)
        print(f"[INFO] Đã thay đổi cat food thành: {save_stats['cat_food']['Value']}")
        
        # Bước 3: Thay đổi inquiry code nếu cần (Chọn 6 > 2)
        new_inquiry = original_inquiry
        inquiry_changed = False
        
        if change_inquiry:
            try:
                # Lấy inquiry code mới từ API
                print("[INFO] Đang lấy inquiry code mới từ API...")
                api_url = 'https://nyanko-backups.ponosgames.com/?action=createAccount&referenceId='
                response = requests.get(api_url)
                
                if response.status_code == 200:
                    data = response.json()
                    new_inquiry = data.get('accountId', '')
                    
                    if new_inquiry:
                        print(f"[INFO] Đã lấy inquiry code mới: {new_inquiry}")
                        # Thay đổi inquiry code (Chọn 6 > 2)
                        save_stats['inquiry_code'] = new_inquiry
                        # Reset token vì inquiry code đã thay đổi
                        save_stats['token'] = "0" * 40
                        print(f"[INFO] Đã thay đổi inquiry code từ {original_inquiry} thành {new_inquiry}")
                        inquiry_changed = True
                    else:
                        print("[INFO] Không thể lấy inquiry code mới từ API (accountId trống)")
                else:
                    print(f"[INFO] Lỗi khi truy cập API: {response.status_code}")
            except Exception as e:
                import traceback
                print(f"[INFO] Lỗi khi thay đổi inquiry code: {str(e)}")
                print(traceback.format_exc())
        
        # Cập nhật lại dữ liệu save file sau khi thay đổi
        print("[INFO] Đang cập nhật lại dữ liệu save file...")
        try:
            from BCSFE_Python import serialise_save
            modified_save_data = serialise_save.start_serialize(save_stats)
        except ImportError:
            print("[INFO] Không thể import serialise_save trực tiếp, thử import từ helper...")
            modified_save_data = helper.serialise_save.start_serialize(save_stats)
            
        # Sử dụng file riêng cho dữ liệu đã chỉnh sửa
        helper.write_file_bytes(modified_save_file, modified_save_data)
        print(f"[INFO] Đã lưu file đã chỉnh sửa tại: {modified_save_file}")
        
        # Bước 4: Upload để lấy mã mới (Chọn 1 > 3 > Enter)
        print("[INFO] Đang upload save data để lấy mã mới...")
        upload_data = server_handler.upload_handler(save_stats, modified_save_file)
        
        if upload_data is None:
            print("[INFO] upload_handler trả về None")
            return jsonify({
                'status': 'error', 
                'message': 'Không thể tải lên máy chủ',
                'debug_info': {
                    'original_inquiry': original_inquiry,
                    'new_inquiry': new_inquiry,
                    'token_reset': save_stats['token'] == "0" * 40,
                    'cat_food_value': save_stats['cat_food']['Value'],
                    'download_path_exists': os.path.exists(modified_save_file),
                    'download_path_size': os.path.getsize(modified_save_file) if os.path.exists(modified_save_file) else 0
                }
            })
        
        upload_data, updated_save_stats = upload_data
        print(f"[INFO] Upload thành công, đã nhận được dữ liệu mới")
        
        if upload_data is None or 'transferCode' not in upload_data:
            print("[INFO] Không tìm thấy transferCode trong dữ liệu upload")
            return jsonify({'status': 'error', 'message': 'Không nhận được mã chuyển giao mới'})
        
        # Kiểm tra lại inquiry code sau khi upload
        final_inquiry = updated_save_stats['inquiry_code']
        print(f"[INFO] Inquiry code sau khi upload: {final_inquiry}")
        
        # Lưu lại kết quả upload cuối cùng vào file
        result_info = {
            'transfer_code': upload_data['transferCode'],
            'confirmation_code': upload_data['pin'],
            'original_inquiry': original_inquiry,
            'final_inquiry': final_inquiry,
            'security_code': security_code,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Lưu thông tin kết quả vào file với mutex
        try:
            with result_mutex:
                result_path = os.path.join(app.config['UPLOAD_FOLDER'], 'latest_transfer_result.json')
                with open(result_path, 'w') as f:
                    json.dump(result_info, f, indent=2)
                print(f"[INFO] Đã lưu thông tin kết quả vào {result_path}")
        except Exception as e:
            print(f"[INFO] Không thể lưu thông tin kết quả: {str(e)}")
        
        # Cập nhật file save data cho API download với mutex
        with file_mutex:
            shared_modified_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modified_save_file.sav')
            with open(modified_save_file, 'rb') as src_file:
                file_content = src_file.read()
                with open(shared_modified_path, 'wb') as dest_file:
                    dest_file.write(file_content)
            print(f"[INFO] Đã cập nhật file save data được chia sẻ tại: {shared_modified_path}")
            
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
                'cat_food': updated_save_stats['cat_food']['Value'],
                'xp': updated_save_stats['xp']['Value'],
                'rare_tickets': updated_save_stats['rare_tickets']['Value'],
                'platinum_tickets': updated_save_stats['platinum_tickets']['Value']
            },
            'original_inquiry': original_inquiry,
            'new_inquiry': final_inquiry,
            'inquiry_changed': original_inquiry != final_inquiry,
            'security_code': security_code,
            'save_data_url': f'/api/download_save_data/{security_code}'
        }
        
        print(f"[INFO] Hoàn thành auto_transfer: {result['status']}")
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[INFO] Lỗi trong auto_transfer: {str(e)}")
        print(error_trace)
        return jsonify({'status': 'error', 'message': f'Lỗi khi xử lý: {str(e)}', 'trace': error_trace})
    finally:
        # Dọn dẹp các file tạm thời
        try:
            if os.path.exists(current_save_file):
                os.remove(current_save_file)
            if os.path.exists(modified_save_file):
                os.remove(modified_save_file)
            print(f"[INFO] Đã dọn dẹp các file tạm thời cho request_id={request_id}")
        except Exception as cleanup_error:
            print(f"[WARNING] Không thể dọn dẹp file tạm: {str(cleanup_error)}")

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
            'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
            'threading_enabled': True
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        })

if __name__ == '__main__':
    # Chạy Flask với threading và số lượng luồng tối đa là 10
    import werkzeug.serving
    from werkzeug.serving import WSGIRequestHandler
    
    # Tăng thời gian timeout cho các kết nối
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    
    print("[INFO] Khởi động server với threading được bật...")
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)