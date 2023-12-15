import dbus

import uuid


# Initialize D-Bus system bus
bus = dbus.SystemBus()

# Get NetworkManager settings and interface objects
settings_proxy = bus.get_object(
    "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager/Settings"
)
settings_iface = dbus.Interface(
    settings_proxy, "org.freedesktop.NetworkManager.Settings"
)

nm_proxy = bus.get_object(
    "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager"
)
nm_iface = dbus.Interface(nm_proxy, "org.freedesktop.NetworkManager")

# Initialize variables
device_path = None
device_proxy = None
device_iface = None
active_connection_path = None
active_connection_proxy = None
active_connection_props = None
current_hotspot_uuid = None


def set_network_interface(iface):
    """
    Set the network interface for the script to operate on.
    """
    global device_path, device_proxy, device_iface
    device_path = nm_iface.GetDeviceByIpIface(iface)
    device_proxy = bus.get_object("org.freedesktop.NetworkManager", device_path)
    device_iface = dbus.Interface(device_proxy, "org.freedesktop.NetworkManager.Device")


def create_hotspot(ssid="Hotspot", passwd=None):
    """
    Create a Wi-Fi hotspot with the specified SSID and optional password.
    """
    global current_hotspot_uuid
    # Create an unique uuid for hotspot
    current_hotspot_uuid = str(uuid.uuid4())

    connection_settings = dbus.Dictionary(
        {"type": "802-11-wireless", "uuid": current_hotspot_uuid, "id": "hotspot"}
    )

    wifi_settings = dbus.Dictionary(
        {
            "ssid": dbus.ByteArray(ssid.encode("utf-8")),
            "mode": "ap",
            "band": "bg",
            "channel": dbus.UInt32(1),
        }
    )

    security_settings = dbus.Dictionary(
        {"key-mgmt": "sae",
         "psk": passwd,
         "pairwise": ["ccmp"],
         "proto": ["rsn"]}
    )

    ip4_settings = dbus.Dictionary({"method": "shared"})
    ip6_settings = dbus.Dictionary({"method": "auto"})

    connection = dbus.Dictionary(
        {
            "connection": connection_settings,
            "802-11-wireless": wifi_settings,
            "802-11-wireless-security": security_settings,
            "ipv4": ip4_settings,
            "ipv6": ip6_settings,
        }
    )

    # Remove existing hotspot connection
    find_and_remove_connection()

    # Add a new connection
    connection_path = settings_iface.AddConnection(connection)

    # Activate the connection
    global active_connection_path, active_connection_proxy, active_connection_props
    active_connection_path = nm_iface.ActivateConnection(
        connection_path, device_path, "/"
    )
    active_connection_proxy = bus.get_object(
        "org.freedesktop.NetworkManager", active_connection_path
    )
    active_connection_props = dbus.Interface(
        active_connection_proxy, "org.freedesktop.DBus.Properties"
    )


def get_connection_state():
    """
    Get the state of the active network connection.
    """
    if active_connection_props is None:
        return 0
    state = active_connection_props.Get(
        "org.freedesktop.NetworkManager.Connection.Active", "State"
    )
    return state


def is_connection_activated():
    """
    Check if the network connection is in the "activated" state.
    """
    return get_connection_state() == 2  # NM_ACTIVE_CONNECTION_STATE_ACTIVATED


def is_wifi_enabled():
    """
    Check if the Wi-Fi hardware is physically enabled.
    """
    nm_props = dbus.Interface(nm_proxy, "org.freedesktop.DBus.Properties")

    # Check the WirelessEnabled property
    wifi_enabled = nm_props.Get("org.freedesktop.NetworkManager", "WirelessEnabled")
    return wifi_enabled


def find_and_remove_connection():
    """
    Find an existing hotspot connection and remove it.
    """
    global current_hotspot_uuid

    for path in settings_iface.ListConnections():
        connection_proxy = bus.get_object("org.freedesktop.NetworkManager", path)
        connection_settings = dbus.Interface(
            connection_proxy, "org.freedesktop.NetworkManager.Settings.Connection"
        ).GetSettings()

        if connection_settings["connection"]["uuid"] == current_hotspot_uuid:
            dbus.Interface(
                connection_proxy, "org.freedesktop.NetworkManager.Settings.Connection"
            ).Delete()

            current_hotspot_uuid = None
            break


def remove_hotspot():
    """
    Disconnect from the hotspot and remove the connection.
    """
    global device_path, device_proxy, device_iface
    global active_connection_path, active_connection_proxy, active_connection_props

    # Check if the device interface is initialized
    if device_iface is None:
        print("No network device interface found.")
        return False

    # Attempt to disconnect
    try:
        device_iface.Disconnect()
    except Exception as e:
        print(f"Error disconnecting the device: {e}")

    find_and_remove_connection()

    # Reset variables
    active_connection_path = None
    active_connection_proxy = None
    active_connection_props = None

    return True
