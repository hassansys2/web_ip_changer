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
        interfaces = {}
        # Get IP addresses
        ip_result = subprocess.run(['ip', '-o', '-4', 'addr', 'show'], stdout=subprocess.PIPE)
        for line in ip_result.stdout.decode('utf-8').split('\n'):
            if line:
                parts = line.split()
                interface = parts[1]
                ip_address = parts[3].split('/')[0]
                interfaces[interface] = {'ip_address': ip_address}

        # Get connection methods (DHCP or static)
        nmcli_result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,IP4,IP4.ADDRESS,IP4.GATEWAY,IP4.METHOD', 'device', 'show'], stdout=subprocess.PIPE)
        for line in nmcli_result.stdout.decode('utf-8').split('\n'):
            if line:
                parts = line.split(':')
                if parts[0] in interfaces:
                    interfaces[parts[0]].update({
                        'method': parts[4],
                        'gateway': parts[3] if parts[4] == 'manual' else None,
                        'netmask': None  # netmask could be parsed from IP address if needed
                    })
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

            command_ip = f"sudo ifconfig {interface} {ip_address} netmask {netmask}"
            command_gw = f"sudo route add default gw {gateway} {interface}"
            
            subprocess.run(command_ip.split(), check=True)
            subprocess.run(command_gw.split(), check=True)

        elif ip_option == 'dhcp':
            command_dhcp = f"sudo dhclient {interface}"
            subprocess.run(command_dhcp.split(), check=True)
        else:
            return jsonify({'error': 'Invalid IP option'}), 400

        return jsonify({'status': 'IP address changed successfully'}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
