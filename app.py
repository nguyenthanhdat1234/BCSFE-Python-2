import os
import tempfile
from flask import Flask, request, jsonify, send_file
import sys
from flask_cors import CORS
import threading
import uuid
import time
import traceback

# Thêm đường dẫn để tìm BCSFE_Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'BCSFE-Python')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'BCSFE-Python', 'src')))

# Global variables for imported modules
helper = None
parse_save = None
server_handler = None
ServerHandler = None
core = None

# Try multiple import strategies
try:
    print("🔄 Trying import strategy 1: Modern BCSFE package...")
    # Strategy 1: Modern BCSFE package (3.0.0b8)
    import bcsfe
    from bcsfe import core
    from bcsfe.core.server import server_handler as sh
    
    # Initialize BCSFE if needed
    try:
        if hasattr(bcsfe, 'setup'):
            bcsfe.setup()
        elif hasattr(core, 'setup'):
            core.setup()
    except:
        pass
    
    # Ensure core_data exists with all needed attributes
    if not hasattr(core, 'core_data') or core.core_data is None:
        print("🔧 Creating mock core_data...")
        
        class MockConfig:
            def get_int(self, key):
                if hasattr(key, 'value'):
                    key_name = key.value
                else:
                    key_name = str(key)
                if 'TIMEOUT' in key_name:
                    return 30
                return 10
            
            def get_str(self, key):
                if hasattr(key, 'value'):
                    key_name = key.value
                else:
                    key_name = str(key)
                return ""
            
            def get_bool(self, key):
                if hasattr(key, 'value'):
                    key_name = key.value
                else:
                    key_name = str(key)
                return False
        
        class MockLogger:
            def log_error(self, text):
                print(f"[ERROR] {text}")
            def log_info(self, text):
                print(f"[INFO] {text}")
        
        class MockLocalManager:
            def __getattr__(self, name):
                def flexible_method(*args, **kwargs):
                    if name.startswith('get_') and ('path' in name or 'key' in name):
                        return ""
                    elif name.startswith('get_') and 'data' in name:
                        return b""
                    elif name.startswith('get_'):
                        return ""
                    return None
                return flexible_method
        
        class MockCoreData:
            def __init__(self):
                self.config = MockConfig()
                self.logger = MockLogger()
                self.local_manager = MockLocalManager()
                self.theme_manager = MockThemeManager()
                
            def __getattr__(self, name):
                """Handle any missing attributes dynamically"""
                print(f"[DEBUG] Missing core_data attribute: {name} - creating mock")
                
                class UniversalMock:
                    def __getattr__(self, attr_name):
                        def flexible_method(*args, **kwargs):
                            print(f"[DEBUG] Mock {name}.{attr_name} called")
                            if attr_name.startswith('get_'):
                                return ""
                            return None
                        return flexible_method
                
                mock_obj = UniversalMock()
                setattr(self, name, mock_obj)
                return mock_obj
        
        class MockThemeManager:
            def __getattr__(self, name):
                def flexible_method(*args, **kwargs):
                    if name.startswith('get_'):
                        return ""
                    return None
                return flexible_method
        
        core.core_data = MockCoreData()
        print("✅ Mock core_data created successfully!")
    
    # Additional check to ensure config exists
    elif not hasattr(core.core_data, 'config') or core.core_data.config is None:
        print("🔧 Adding missing config to existing core_data...")
        
        class MockConfig:
            def get_int(self, key):
                if hasattr(key, 'value'):
                    key_name = key.value
                else:
                    key_name = str(key)
                if 'TIMEOUT' in key_name:
                    return 30
                return 10
            
            def get_str(self, key):
                return ""
            
            def get_bool(self, key):
                return False
        
        core.core_data.config = MockConfig()
        print("✅ Config added to existing core_data!")
        
    # Ensure local_manager exists
    if not hasattr(core.core_data, 'local_manager') or core.core_data.local_manager is None:
        print("🔧 Adding missing local_manager...")
        
        class MockLocalManager:
            def __getattr__(self, name):
                def flexible_method(*args, **kwargs):
                    if name.startswith('get_') and ('path' in name or 'key' in name):
                        return ""
                    elif name.startswith('get_') and 'data' in name:
                        return b""
                    elif name.startswith('get_'):
                        return ""
                    return None
                return flexible_method
        
        core.core_data.local_manager = MockLocalManager()
        print("✅ Local manager added!")
        
    # Ensure logger exists  
    if not hasattr(core.core_data, 'logger') or core.core_data.logger is None:
        print("🔧 Adding missing logger...")
        
        class MockLogger:
            def log_error(self, text):
                print(f"[ERROR] {text}")
            def log_info(self, text):
                print(f"[INFO] {text}")
        
        core.core_data.logger = MockLogger()
        print("✅ Logger added!")
        
    # Ensure theme_manager exists
    if not hasattr(core.core_data, 'theme_manager') or core.core_data.theme_manager is None:
        print("🔧 Adding missing theme_manager...")
        
        class MockThemeManager:
            def __getattr__(self, name):
                def flexible_method(*args, **kwargs):
                    if name.startswith('get_'):
                        return ""
                    return None
                return flexible_method
        
        core.core_data.theme_manager = MockThemeManager()
        print("✅ Theme manager added!")
    
    ServerHandler = sh.ServerHandler
    
    # Modern BCSFE functions
    def download_save_modern(country_code, transfer_code, confirmation_code, game_version):
        try:
            cc = core.CountryCode.from_code(country_code.upper())
            gv = core.GameVersion.from_string(str(game_version))
            server_handler_instance, request_result = ServerHandler.from_codes(
                transfer_code, confirmation_code, cc, gv, print=False, save_backup=False
            )
            if server_handler_instance is None:
                return None, request_result
            return server_handler_instance.save_file, server_handler_instance
        except Exception as e:
            print(f"[ERROR] Modern download failed: {e}")
            return None, None
    
    def upload_save_modern(save_file_obj, server_handler_instance):
        try:
            result = server_handler_instance.get_codes(upload_managed_items=True)
            if result is None:
                return None
            transfer_code, confirmation_code = result
            return {
                'transferCode': transfer_code,
                'pin': confirmation_code
            }
        except Exception as e:
            print(f"[ERROR] Modern upload failed: {e}")
            return None
    
    print("✅ Modern BCSFE package import successful!")
    IMPORT_MODE = "modern"
    
except ImportError as e1:
    print(f"❌ Modern import failed: {e1}")
    
    try:
        print("🔄 Trying import strategy 2: Legacy BCSFE_Python...")
        # Strategy 2: Legacy BCSFE_Python
        from BCSFE_Python import helper, parse_save, server_handler
        
        def download_save_legacy(country_code, transfer_code, confirmation_code, game_version):
            try:
                # Check and format codes
                transfer_code = helper.check_hex(transfer_code.lower().replace("o", "0"))
                confirmation_code = helper.check_dec(confirmation_code.lower().replace("o", "0"))
                
                if not transfer_code or not confirmation_code:
                    return None, None
                
                # Download save
                numeric_game_version = helper.str_to_gv(str(game_version))
                response = server_handler.download_save(
                    country_code, transfer_code, confirmation_code, numeric_game_version
                )
                
                save_data = response.content
                if not server_handler.test_is_save_data(save_data):
                    return None, None
                
                # Parse save
                save_stats = parse_save.start_parse(save_data, country_code)
                headers = response.headers
                save_stats['token'] = headers.get('nyanko-password-refresh-token', '')
                
                return save_stats, None
            except Exception as e:
                print(f"[ERROR] Legacy download failed: {e}")
                return None, None
        
        def upload_save_legacy(save_stats, save_file_path):
            try:
                # Serialize save
                try:
                    from BCSFE_Python import serialise_save
                    modified_save_data = serialise_save.start_serialize(save_stats)
                except ImportError:
                    modified_save_data = helper.serialise_save.start_serialize(save_stats)
                
                # Write to file
                helper.write_file_bytes(save_file_path, modified_save_data)
                
                # Upload
                upload_data = server_handler.upload_handler(save_stats, save_file_path)
                if upload_data is None:
                    return None
                
                upload_result, updated_save_stats = upload_data
                return upload_result
            except Exception as e:
                print(f"[ERROR] Legacy upload failed: {e}")
                return None
        
        print("✅ Legacy BCSFE_Python import successful!")
        IMPORT_MODE = "legacy"
        
    except ImportError as e2:
        print(f"❌ All import strategies failed:")
        print(f"   - Modern: {e1}")
        print(f"   - Legacy: {e2}")
        print("📝 Please install BCSFE: pip install bcsfe==3.0.0b8")
        sys.exit(1)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Tạo mutex cho các hoạt động truy cập file
file_mutex = threading.Lock()
result_mutex = threading.Lock()

# Thiết lập CORS
ALLOWED_ORIGINS = [
    'http://example.com',
    'https://example.com',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'https://bcsfe-web-app.onrender.com',
    'http://localhost:54216'
]

CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

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

# Thư mục lưu trữ file tạm thời
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'bcsfe_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/api/download_save_data/<security_code>', methods=['GET'])
def download_save_data(security_code):
    try:
        modified_save_path = os.path.join(app.config['UPLOAD_FOLDER'], f'modified_save_file_{security_code}.sav')
        
        if not os.path.exists(modified_save_path):
            return jsonify({'status': 'error', 'message': 'Không tìm thấy file save data'}), 404
        
        with file_mutex:
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'download_copy_{security_code}_{uuid.uuid4()}.sav')
            with open(modified_save_path, 'rb') as src_file:
                file_content = src_file.read()
                with open(temp_file_path, 'wb') as dest_file:
                    dest_file.write(file_content)
        
        response = send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f'{security_code}_SAVE_DATA.sav',
            mimetype='application/octet-stream'
        )
        
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                print(f"[WARNING] Không thể xóa file tạm thời: {str(e)}")
        
        return response
        
    except Exception as e:
        print(f"[ERROR] Lỗi khi tải xuống file save data: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error', 
            'message': f'Lỗi khi tải file: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/auto_transfer', methods=['POST'])
def auto_transfer():
    request_id = str(uuid.uuid4())
    
    try:
        import datetime
        import json
        import requests
        
        # Lấy dữ liệu đầu vào
        transfer_code = request.form.get('transfer_code', '').strip()
        confirmation_code = request.form.get('confirmation_code', '').strip()
        country_code = request.form.get('country_code', 'en').strip()
        game_version = request.form.get('game_version', '13.10.0').strip()
        cat_food = request.form.get('cat_food', None)
        change_inquiry = request.form.get('change_inquiry', 'true').lower() == 'true'
        security_code = request.form.get('security_code', '1').strip()
        
        print(f"[INFO] Auto transfer started - Mode: {IMPORT_MODE}, Request ID: {request_id}")
        print(f"[INFO] Transfer code: {transfer_code}, Confirmation: {confirmation_code}")
        
        if not transfer_code or not confirmation_code:
            return jsonify({'status': 'error', 'message': 'Mã chuyển giao và mã xác nhận là bắt buộc'})
        
        # Bước 1: Download save data
        print(f"[INFO] Downloading save data using {IMPORT_MODE} mode...")
        
        if IMPORT_MODE == "modern":
            save_data_obj, server_handler_instance = download_save_modern(
                country_code, transfer_code, confirmation_code, game_version
            )
            
            if save_data_obj is None:
                return jsonify({'status': 'error', 'message': 'Không thể tải save data. Kiểm tra mã chuyển giao/xác nhận.'})
            
            # Get original values
            original_values = {
                'cat_food': save_data_obj.catfood,
                'xp': save_data_obj.xp,
                'rare_tickets': save_data_obj.rare_tickets,
                'platinum_tickets': save_data_obj.platinum_tickets,
                'legend_tickets': save_data_obj.legend_tickets
            }
            original_inquiry = save_data_obj.inquiry_code
            
            # Modify cat food
            if cat_food is None:
                cat_food = 19999 if security_code == '1' else (18000 if security_code == '2' else 2000)
            save_data_obj.catfood = int(cat_food)
            
            # Change inquiry if needed
            new_inquiry = original_inquiry
            inquiry_changed = False
            
            if change_inquiry:
                try:
                    print("[INFO] Getting new inquiry code...")
                    api_url = 'https://nyanko-backups.ponosgames.com/?action=createAccount&referenceId='
                    response = requests.get(api_url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        new_inquiry_code = data.get('accountId', '')
                        
                        if new_inquiry_code:
                            save_data_obj.inquiry_code = new_inquiry_code
                            new_inquiry = new_inquiry_code
                            inquiry_changed = True
                            print(f"[INFO] Changed inquiry code: {original_inquiry} → {new_inquiry}")
                            
                            # Reset tokens
                            server_handler_instance.remove_stored_auth_token()
                            server_handler_instance.remove_stored_save_key_data()
                            server_handler_instance.remove_stored_password()
                except Exception as e:
                    print(f"[INFO] Error changing inquiry code: {e}")
            
            # Upload to get new codes
            print("[INFO] Uploading save data...")
            upload_result = upload_save_modern(save_data_obj, server_handler_instance)
            
            if upload_result is None:
                return jsonify({'status': 'error', 'message': 'Không thể upload save data'})
            
            # Save file for download
            modified_save_file = os.path.join(app.config['UPLOAD_FOLDER'], f'modified_save_file_{security_code}.sav')
            with file_mutex:
                try:
                    save_data_bytes = save_data_obj.to_data()
                    with open(modified_save_file, 'wb') as f:
                        f.write(save_data_bytes.data)
                except Exception as e:
                    print(f"[ERROR] Error saving file: {e}")
            
            final_values = {
                'cat_food': save_data_obj.catfood,
                'xp': save_data_obj.xp,
                'rare_tickets': save_data_obj.rare_tickets,
                'platinum_tickets': save_data_obj.platinum_tickets,
                'legend_tickets': save_data_obj.legend_tickets
            }
            
        else:  # legacy mode
            save_stats, _ = download_save_legacy(
                country_code, transfer_code, confirmation_code, game_version
            )
            
            if save_stats is None:
                return jsonify({'status': 'error', 'message': 'Không thể tải save data. Kiểm tra mã chuyển giao/xác nhận.'})
            
            # Get original values
            original_values = {
                'cat_food': save_stats['cat_food']['Value'],
                'xp': save_stats['xp']['Value'],
                'rare_tickets': save_stats['rare_tickets']['Value'],
                'platinum_tickets': save_stats['platinum_tickets']['Value']
            }
            original_inquiry = save_stats['inquiry_code']
            
            # Modify cat food
            if cat_food is None:
                cat_food = 19999 if security_code == '1' else (18000 if security_code == '2' else 2000)
            save_stats['cat_food']['Value'] = int(cat_food)
            
            # Change inquiry if needed
            new_inquiry = original_inquiry
            inquiry_changed = False
            
            if change_inquiry:
                try:
                    print("[INFO] Getting new inquiry code...")
                    api_url = 'https://nyanko-backups.ponosgames.com/?action=createAccount&referenceId='
                    response = requests.get(api_url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        new_inquiry_code = data.get('accountId', '')
                        
                        if new_inquiry_code:
                            save_stats['inquiry_code'] = new_inquiry_code
                            save_stats['token'] = "0" * 40
                            new_inquiry = new_inquiry_code
                            inquiry_changed = True
                            print(f"[INFO] Changed inquiry code: {original_inquiry} → {new_inquiry}")
                except Exception as e:
                    print(f"[INFO] Error changing inquiry code: {e}")
            
            # Upload to get new codes
            print("[INFO] Uploading save data...")
            modified_save_file = os.path.join(app.config['UPLOAD_FOLDER'], f'modified_save_file_{security_code}.sav')
            upload_result = upload_save_legacy(save_stats, modified_save_file)
            
            if upload_result is None:
                return jsonify({'status': 'error', 'message': 'Không thể upload save data'})
            
            final_values = {
                'cat_food': save_stats['cat_food']['Value'],
                'xp': save_stats['xp']['Value'],
                'rare_tickets': save_stats['rare_tickets']['Value'],
                'platinum_tickets': save_stats['platinum_tickets']['Value']
            }
        
        # Prepare result
        result = {
            'status': 'success',
            'message': 'Đã tạo mã chuyển giao mới thành công',
            'mode': IMPORT_MODE,
            'old_transfer_code': transfer_code,
            'old_confirmation_code': confirmation_code,
            'new_transfer_code': upload_result['transferCode'],
            'new_confirmation_code': upload_result['pin'],
            'original_values': original_values,
            'modified_values': final_values,
            'original_inquiry': original_inquiry,
            'new_inquiry': new_inquiry,
            'inquiry_changed': inquiry_changed,
            'security_code': security_code,
            'save_data_url': f'/api/download_save_data/{security_code}'
        }
        
        # Save result info
        try:
            with result_mutex:
                result_path = os.path.join(app.config['UPLOAD_FOLDER'], 'latest_transfer_result.json')
                with open(result_path, 'w') as f:
                    json.dump(result, f, indent=2)
        except Exception as e:
            print(f"[INFO] Could not save result info: {e}")
        
        print(f"[INFO] Auto transfer completed successfully!")
        return jsonify(result)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[ERROR] Error in auto_transfer: {str(e)}")
        print(error_trace)
        return jsonify({
            'status': 'error', 
            'message': f'Lỗi khi xử lý: {str(e)}', 
            'trace': error_trace
        }), 500

@app.route('/')
def index():
    return f"🐱 BCSFE API v2.0 ({IMPORT_MODE} mode) hoạt động bình thường. Sử dụng /api/auto_transfer với phương thức POST."

@app.route('/test')
def test():
    try:
        return jsonify({
            'status': 'success',
            'message': 'Hệ thống hoạt động bình thường',
            'import_mode': IMPORT_MODE,
            'import_status': f'Đã import BCSFE ({IMPORT_MODE}) thành công',
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
            'threading_enabled': True,
            'available_endpoints': [
                'POST /api/auto_transfer',
                'GET /api/download_save_data/<security_code>',
                'GET /test',
                'GET /api/health'
            ]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Lỗi: {str(e)}',
            'traceback': traceback.format_exc()
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'mode': IMPORT_MODE,
        'timestamp': time.time(),
        'version': '2.0.0'
    })

if __name__ == '__main__':
    import werkzeug.serving
    from werkzeug.serving import WSGIRequestHandler
    
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    
    print(f"[INFO] 🚀 Starting BCSFE API v2.0 in {IMPORT_MODE} mode...")
    print("[INFO] 📋 Available endpoints:")
    print("[INFO]   - POST /api/auto_transfer")
    print("[INFO]   - GET  /api/download_save_data/<security_code>")
    print("[INFO]   - GET  /test")
    print("[INFO]   - GET  /api/health")
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)