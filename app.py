from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import yaml
import os
import re

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

NETPLAN_CONFIG_PATH = '/etc/netplan/01-netcfg.yaml'
INTERFACE = 'eth0'

def get_network_interface():
    interface = {}
    try:
        result = subprocess.run(['ip', 'addr', 'show', INTERFACE], capture_output=True, text=True, check=True)
        output = result.stdout
        ip_address, netmask, gateway = None, None, None
        
        # Extract IP address and netmask
        ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/(\d+)', output)
        if ip_match:
            ip_address = ip_match.group(1)
            netmask = ip_match.group(2)

        # Extract gateway
        route_result = subprocess.run(['ip', 'route', 'show', 'default', 'dev', INTERFACE], capture_output=True, text=True, check=True)
        route_output = route_result.stdout
        gateway_match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', route_output)
        if gateway_match:
            gateway = gateway_match.group(1)
        
        # Check if DHCP is enabled
        dhcp = False
        if os.path.exists(NETPLAN_CONFIG_PATH):
            with open(NETPLAN_CONFIG_PATH, 'r') as file:
                netplan_config = yaml.safe_load(file)
                config = netplan_config.get('network', {}).get('ethernets', {}).get(INTERFACE, {})
                dhcp = config.get('dhcp4', False)

        interface = {
            'ip_address': ip_address,
            'netmask': netmask,
            'gateway': gateway,
            'dhcp': dhcp
        }

        return interface

    except subprocess.CalledProcessError as e:
        print(f"Subprocess error: {str(e)}")
    except yaml.YAMLError as e:
        print(f"Error parsing Netplan configuration: {str(e)}")
    except Exception as e:
        print(f"Error fetching network interface: {str(e)}")
    return interface

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/interface', methods=['GET'])
def interface():
    interface = get_network_interface()
    if not interface:
        return jsonify({'error': 'Failed to fetch network interface'}), 500
    return jsonify({'interface': interface}), 200

@app.route('/change_ip', methods=['POST'])
def change_ip():
    data = request.json
    ip_option = data.get('ip_option')

    if not ip_option:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        if os.path.exists(NETPLAN_CONFIG_PATH):
            with open(NETPLAN_CONFIG_PATH, 'r') as file:
                netplan_config = yaml.safe_load(file)
        else:
            netplan_config = {'network': {'version': 2, 'ethernets': {}}}

        if 'network' not in netplan_config:
            netplan_config['network'] = {}
        if 'ethernets' not in netplan_config['network']:
            netplan_config['network']['ethernets'] = {}
        if INTERFACE not in netplan_config['network']['ethernets']:
            netplan_config['network']['ethernets'][INTERFACE] = {}

        iface_config = netplan_config['network']['ethernets'][INTERFACE]

        if ip_option == 'static':
            ip_address = data.get('ip_address')
            netmask = data.get('netmask')
            gateway = data.get('gateway')

            if not ip_address or not netmask or not gateway:
                return jsonify({'error': 'Missing required parameters for static IP'}), 400

            iface_config['addresses'] = [f"{ip_address}/{netmask}"]
            iface_config['routes'] = [{'to': '0.0.0.0/0', 'via': gateway}]
            iface_config['dhcp4'] = False

        elif ip_option == 'dhcp':
            iface_config['dhcp4'] = True
            iface_config.pop('addresses', None)
            iface_config.pop('routes', None)
        else:
            return jsonify({'error': 'Invalid IP option'}), 400

        with open(NETPLAN_CONFIG_PATH, 'w') as file:
            yaml.safe_dump(netplan_config, file)

        subprocess.run(['sudo', 'netplan', 'apply'], check=True)

        return jsonify({'status': 'IP address changed successfully'}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f"Subprocess error: {str(e)}"}), 500
    except FileNotFoundError as e:
        return jsonify({'error': f"File not found: {str(e)}"}), 500
    except yaml.YAMLError as e:
        return jsonify({'error': f"YAML error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': f"General error: {str(e)}"}), 500

@app.route('/change_time', methods=['POST'])
def change_time():
    data = request.json
    time_option = data.get('time_option')

    if not time_option:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        if time_option == 'manual':
            date = data.get('date')
            time = data.get('time')
            if not date or not time:
                return jsonify({'error': 'Missing required parameters for manual time setting'}), 400

            subprocess.run(['sudo', 'timedatectl', 'set-time', f"{date} {time}"], check=True)
        
        elif time_option == 'ntp':
            ntp_server = data.get('ntp_server', 'pool.ntp.org')
            subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'true'], check=True)
            # subprocess.run(['sudo', 'timedatectl', 'set-timezone', '<your_timezone>'], check=True)  # Replace <your_timezone> with your actual timezone
            # subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-timesyncd'], check=True)  # Use systemd-timesyncd for time synchronization
        
        else:
            return jsonify({'error': 'Invalid time option'}), 400

        return jsonify({'status': 'Time configuration changed successfully'}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f"Subprocess error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': f"General error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
