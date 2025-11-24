# 🚀 GMoni

A command-line GPU monitoring dashboard built with Python `asyncio` and `rich`. Designed for deep learning clusters, it enables real-time monitoring of basic NVIDIA GPU status across multiple remote Linux servers via SSH.

## 🛠️ Prerequisites

* Python 3.8+
* Install the `rich` library locally:
    ```bash
    pip install rich
    ```
* **SSH Passwordless Login**: Ensure you can connect to your remote servers directly using SSH keys without entering a password.

## ⚙️ Configuration

### 1. SSH Config (`~/.ssh/config`)
This project relies on your local SSH configuration file to manage host aliases, ports, and keys.

```ssh
# Example configuration:
Host server1
    HostName 192.168.1.100
    Port 9300
    User root
    IdentityFile ~/.ssh/id_rsa

Host server2
    HostName 192.168.1.101
    Port 9301
    User root
    IdentityFile ~/.ssh/id_rsa
# ... other servers
````

### 2. Script Config (`gpu_monitor.py`)

Open the script file and modify the `SERVERS` list at the top to match your SSH Host aliases defined above:

```python
# Define server aliases to monitor (must match entries in ~/.ssh/config)
SERVERS = ["server1", "server2"]

# Optional Configuration
REFRESH_RATE = 3   # Refresh interval (seconds)
SSH_TIMEOUT = 20   # Initial connection timeout
```

## 🚀 Usage

Run the script directly in your terminal:

```bash
python gpu_monitor.py
```

* **Exit**: Press `Ctrl + C`.

## 🔍 Troubleshooting

* **Stuck on "Connecting..."**:

  * The initial connection may take 10-20 seconds to establish the SSH multiplexing channel (ControlMaster). Please be patient.
  * The script attempts to disable GSSAPI (DNS lookup) by default to speed up connections.
* **Shows "CONNECTION FAILED"**:

  * **Timed Out**: Check if the firewall allows traffic on the specified port, or if the IP address is correct.
  * **Connection Refused**: There is no SSH service running on the target port.

## 📝 Note

Keep curious, enjoy yourself!
