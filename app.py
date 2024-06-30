from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import gi

gi.require_version('NM', '1.0')
from gi.repository import NM

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/interfaces', methods=['GET'])
def get_interfaces():
    try:
        client = NM.Client.new(None)
        devices = client.get_devices()
        interfaces = [dev.get_iface() for dev in devices if dev.get_device_type() == NM.DeviceType.ETHERNET]
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

    if ip_option == 'static':
        ip_address = data.get('ip_address')
        netmask = data.get('netmask')
        gateway = data.get('gateway')

        if not ip_address or not netmask or not gateway:
            return jsonify({'error': 'Missing required parameters for static IP'}), 400

        try:
            client = NM.Client.new(None)
            connections = client.get_connections()
            eth_connection = None

            # Find the Ethernet connection matching the interface name
            for conn in connections:
                if conn.get_connection_type() == NM.SettingsConnection.TYPE_WIRED and conn.get_interface_name() == interface:
                    eth_connection = conn
                    break

            if not eth_connection:
                return jsonify({'error': f'No wired connection found for interface {interface}'}), 404

            settings = eth_connection.get_setting_wired()
            settings.set_property(NM.SETTING_WIRED_IP4_CONFIG, {
                'method': NM.SETTING_IP4_CONFIG_METHOD_MANUAL,
                'addresses': [(ip_address, int(netmask))],
                'gateway': gateway
            })
            eth_connection.commit_changes()

            # Activate the connection
            client.activate_connection(eth_connection, None, "/")

            return jsonify({'status': 'IP address changed successfully'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif ip_option == 'dhcp':
        try:
            client = NM.Client.new(None)
            connections = client.get_connections()
            eth_connection = None

            # Find the Ethernet connection matching the interface name
            for conn in connections:
                if conn.get_connection_type() == NM.SettingsConnection.TYPE_WIRED and conn.get_interface_name() == interface:
                    eth_connection = conn
                    break

            if not eth_connection:
                return jsonify({'error': f'No wired connection found for interface {interface}'}), 404

            settings = eth_connection.get_setting_wired()
            settings.set_property(NM.SETTING_WIRED_IP4_CONFIG, {
                'method': NM.SETTING_IP4_CONFIG_METHOD_AUTO,
            })
            eth_connection.commit_changes()

            # Activate the connection
            client.activate_connection(eth_connection, None, "/")

            return jsonify({'status': 'Obtaining IP address automatically (DHCP)'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    else:
        return jsonify({'error': 'Invalid IP option'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
