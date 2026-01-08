import subprocess
import ipaddress
from config import settings
import logging

logger = logging.getLogger(__name__)

class VpnService:
    def __init__(self):
        self.interface = settings.VPN_INTERFACE
        self.subnet = ipaddress.ip_network(settings.VPN_SUBNET)
        self.server_host = settings.VPN_HOST
        self.server_port = settings.VPN_PORT
        
        # Obfuscation params
        self.jc = settings.AMNEZIA_JC
        self.jmin = settings.AMNEZIA_JMIN
        self.jmax = settings.AMNEZIA_JMAX
        self.s1 = settings.AMNEZIA_S1
        self.s2 = settings.AMNEZIA_S2
        self.h1 = settings.AMNEZIA_H1
        self.h2 = settings.AMNEZIA_H2
        self.h3 = settings.AMNEZIA_H3
        self.h4 = settings.AMNEZIA_H4

    def check_awg_installed(self) -> bool:
        try:
            subprocess.run(["awg", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def check_interface(self) -> bool:
        try:
            # Check if interface exists
            subprocess.run(["ip", "link", "show", self.interface], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_command(self, command: list) -> str:
        try:
            logger.debug(f"Running command: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            logger.debug(f"Command output: {result.stdout.strip()[:100]}")
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.cmd}. Error: {e.stderr}")
            raise Exception(f"VPN Command Error: {e.stderr}")

    def generate_keys(self):
        private_key = self._run_command(["awg", "genkey"])
        
        proc = subprocess.Popen(["awg", "pubkey"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pub_out, pub_err = proc.communicate(input=private_key)
        
        if proc.returncode != 0:
             raise Exception(f"Key generation failed: {pub_err}")
             
        return private_key, pub_out.strip()

    def get_next_ip(self, used_ips: list) -> str:
        """Finds the next available IP in the subnet."""
        # Skip network address and gateway (usually .1)
        hosts = list(self.subnet.hosts())
        # Assuming .1 is the server
        available_hosts = hosts[1:] 
        
        used_ips_set = set(ipaddress.ip_address(ip) for ip in used_ips)
        
        for ip in available_hosts:
            if ip not in used_ips_set:
                return str(ip)
        raise Exception("No IP addresses available in subnet")

    def add_peer(self, public_key: str, allowed_ip: str):
        """Adds a peer to the interface."""
        # awg set <interface> peer <pubkey> allowed-ips <ip>/32
        cmd = [
            "awg", "set", self.interface,
            "peer", public_key,
            "allowed-ips", f"{allowed_ip}/32"
        ]
        logger.info(f"Adding peer: {public_key[:10]}... with IP {allowed_ip}")
        self._run_command(cmd)

    def remove_peer(self, public_key: str):
        """Removes a peer from the interface."""
        cmd = [
            "awg", "set", self.interface,
            "peer", public_key,
            "remove"
        ]
        logger.info(f"Removing peer: {public_key[:10]}...")
        self._run_command(cmd)

    def restore_peers(self, peers: list):
        """Restores peers from database to the interface."""
        # peers is a list of dicts/objects with public_key and ip_address
        if not self.check_interface():
            logger.warning(f"Interface {self.interface} not found. Cannot restore peers.")
            return

        logger.info(f"Restoring {len(peers)} peers...")
        for peer in peers:
            try:
                # Handle both dict and Row objects
                public_key = peer['public_key'] if isinstance(peer, dict) else peer.public_key
                ip_address = peer['ip_address'] if isinstance(peer, dict) else peer.ip_address
                self.add_peer(public_key, ip_address)
            except Exception as e:
                pub_key = peer['public_key'] if isinstance(peer, dict) else peer.public_key
                logger.error(f"Failed to restore peer {pub_key}: {e}")

    def generate_client_config(self, private_key: str, client_ip: str, server_pubkey: str) -> str:
        """Generates the AmneziaWG config file content."""
        return f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = {settings.VPN_DNS}
Jc = {self.jc}
Jmin = {self.jmin}
Jmax = {self.jmax}
S1 = {self.s1}
S2 = {self.s2}
H1 = {self.h1}
H2 = {self.h2}
H3 = {self.h3}
H4 = {self.h4}

[Peer]
PublicKey = {server_pubkey}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {self.server_host}:{self.server_port}
PersistentKeepalive = 25
"""

    def get_server_pubkey(self) -> str:
        """Retrieves the server's public key."""
        if not self.check_interface():
             raise Exception(f"Interface {self.interface} does not exist or is down.")
        # awg show <interface> public-key
        pubkey = self._run_command(["awg", "show", self.interface, "public-key"])
        logger.info(f"Retrieved server public key: {pubkey[:10]}...")
        return pubkey

vpn_service = VpnService()
