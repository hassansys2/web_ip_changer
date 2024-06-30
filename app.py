from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/interfaces', methods=['GET'])
def get_interfaces():
    try:
        result = subprocess.run(['nmcli', 'device', 'status'], stdout=subprocess.PIPE)
        interfaces = []
        for line in result.stdout.decode('utf-8').split('\n'):
            if line:
                parts = line.split()
                if parts and parts[1] == 'ethernet':
                    interfaces.append(parts[0])
        return jsonify({'interfaces': interfaces}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/change_ip', methods=['POST'])
def change_ip():
    data = request.json
    interface = data.get('interface')
    ip_option = data.get('ip_option')

    if not interface or not ip_option:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        if ip_option == 'static':
            ip_address = data.get('ip_address')
            netmask = data.get('netmask')
            gateway = data.get('gateway')

            if not ip_address or not netmask or not gateway:
                return jsonify({'error': 'Missing required parameters for static IP'}), 400

            subprocess.run(['nmcli', 'con', 'add', 'type', 'ethernet', 'con-name', 'static-ip', 'ifname', interface,
                            'ip4', f'{ip_address}/{netmask}', 'gw4', gateway], check=True)
            subprocess.run(['nmcli', 'con', 'up', 'static-ip'], check=True)

        elif ip_option == 'dhcp':
            subprocess.run(['nmcli', 'con', 'mod', interface, 'ipv4.method', 'auto'], check=True)
            subprocess.run(['nmcli', 'con', 'up', interface], check=True)
        else:
            return jsonify({'error': 'Invalid IP option'}), 400

        return jsonify({'status': 'IP address changed successfully'}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
