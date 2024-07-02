from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template
from flask_cors import CORS
import subprocess
import logging
import yaml
import os
import re
import json
from functools import wraps
from datetime import datetime, timedelta, timezone

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)
app.secret_key = 'your_secret_key'  # Replace with your own secret key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=60)

# Path to the JSON file storing passwords
PASSWORD_FILE = 'users.json'

# Function to load user data from JSON file
def load_users():
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, 'r') as f:
            return json.load(f)
    return {}

# Function to save user data to JSON file
def save_users(users_data):
    with open(PASSWORD_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

# Dummy user data (replace with your actual user authentication logic)
users = load_users()


@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Missing required parameters'}), 400

    # Replace this with your actual authentication logic
    if 'username' not in session or session['username'] not in users:
        return jsonify({'error': 'User not authenticated or does not exist'}), 401

    username = session['username']
    if users[username]['password'] != current_password:
        return jsonify({'error': 'Current password is incorrect'}), 401

    users[username]['password'] = new_password  # Update password in memory

    save_users(users)  # Save updated user data to file

    return jsonify({'status': 'Password changed successfully'}), 200

def session_expired():
    return 'last_activity' not in session or \
           (datetime.now(timezone.utc) - session['last_activity']) > app.config['PERMANENT_SESSION_LIFETIME']

def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session_expired():
            return redirect(url_for('login'))
        session['last_activity'] = datetime.now(timezone.utc)
        return f(*args, **kwargs)
    return decorated_function

# Dummy user credentials
USERNAME = 'admin'
PASSWORD = 'password'

# Function to check if the user is logged in
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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

@app.route('/login', methods=['GET'])
def login_page():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/')
@session_required
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    if username in users and users[username]['password'] == password:
        session['username'] = username
        return jsonify({'status': 'Login successful'}), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login_page'))

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
            timezone = data.get('timezone')
            if not date or not time or not timezone:
                return jsonify({'error': 'Missing required parameters for manual time setting'}), 400
            
            subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'false'], check=True)
            subprocess.run(['sudo', 'timedatectl', 'set-time', f"{date} {time}"], check=True)
            subprocess.run(['sudo', 'timedatectl', 'set-timezone', timezone], check=True)
        
        elif time_option == 'ntp':
            ntp_server = data.get('ntp_server', 'pool.ntp.org')
            timezone = data.get('timezone')
            if not timezone:
                return jsonify({'error': 'Missing required parameters for NTP setting'}), 400

            subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'true'], check=True)
            subprocess.run(['sudo', 'timedatectl', 'set-timezone', timezone], check=True)
            subprocess.run(['sudo', 'bash', '-c', f"echo 'NTP={ntp_server}' >> /etc/systemd/timesyncd.conf"], check=True)
            subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-timesyncd'], check=True)
        
        else:
            return jsonify({'error': 'Invalid time option'}), 400

        return jsonify({'status': 'Time configuration changed successfully'}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f"Subprocess error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': f"General error: {str(e)}"}), 500

@app.route('/list_timezones', methods=['GET'])
def list_timezones():
    try:
        result = subprocess.run(['timedatectl', 'list-timezones'], capture_output=True, text=True, check=True)
        timezones = result.stdout.splitlines()
        return jsonify({'timezones': timezones}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f"Subprocess error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
