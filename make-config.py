#!/usr/bin/env python3
import requests
import configparser
import multiprocessing
from os.path import isfile

first_run = '''
--- INFO ---
1. How to use it
It seems that you re running this script for the first time.
What do you have to do?
Right now a template file is created --> .env
Fill in the variables in th section credentials, network, server and optional.
After you did this, run it again and the auto-section will populate with infos.

2. How the networking works
Ports are calculated like this:
Number of ports = starting_port * 2 + 1
Each server instance needs 1 game- & 1 voiceport.
One additional port is used as ping port, so your instances can be found by auto-region.
If you re just testing, set region to Newerth and do not forward the first port in your router.
That will make your games only available for public games.
Setting it to a specific region (like EU) will make it available for the EU-region.
Forwarding the ping-port makes it available for tmm regardless of your region, since
the latency is the parameter if somebody sees your server or not.

3. Optional: use_metricbeat
On the first run it will generate client certificates for the stats website made by Frank.
You will be asked to provide the generated Certificate Signing Request - client.csr
Send it to him via Discord: https://discordapp.com/users/197967989964800000
Frank will send the client.pem back, which belongs to your docker volume.
The docker volume can be found by: sudo docker inspect kongor_online | grep volume
Certificates are stored in the filebeat volume.
NOTE: You need root rights for this.
--- INFO END ---
'''


class configGenerator():
    def __init__(self):
        self.config_filename = ".env"
        self.config = configparser.ConfigParser()
        if not isfile(".env"):
            self.write_sample_config()
        self.config.read(self.config_filename)

        self.username = self.config.get("credentials", "username")
        self.password = self.config.get("credentials", "password")
        self.starting_port = int(self.config.get("network", "starting_port"))
        self.server_name = self.config.get("server", "server_name")
        self.number_of_slaves = int(self.config.get("server", "number_of_slaves"))
        self.servers_per_core = self.config.get("server", "servers_per_core")
        self.region = self.config.get("server", "region")
        self.use_metricbeat = self.config.get("optional", "use_metricbeat")
        self.max_cpu = multiprocessing.cpu_count()
        self.ip = requests.get("https://ifconfig.me").text
        self.auto_section = {}

    def _validate_ports(self):
        return 19000 < self.starting_port < 50000


    def write_sample_config(self):
        self.config["global"] = {"dummy" : "dont use" }
        self.config["credentials"] = {
            "username" : "UsernameDummy",
            "password" : "PasswordDummy"
        }
        self.config["network"] = { "starting_port" : 19999 }
        self.config["server"] = {
            "server_name" : "ServerNameDummy",
            "servers_per_core" : 1,
            "number_of_slaves" : 1,
            "region" : "EU/USE/USW/AU/SEA/NEWERTH"
        }
        self.config["optional"] = { "use_metricbeat" : "true/false-Dummy"}
        self.config["auto"] = { "nodata" : "nodata" }

        with open(self.config_filename, "w") as f:
            self.config.write(f, space_around_delimiters=False)
        print(first_run)
        print("Sample configuration created.")
        print("Adjust values and run again")
        exit()


    def prepare_config(self, key, value):
        self.config.set("auto", str(key), str(value))
        self.write_config()

    def write_config(self):
        with open(self.config_filename, "w") as f:
            self.config.write(f, space_around_delimiters=False)

    def calculate_ports(self):
        if not self._validate_ports():
            print("use a starting port between 19.000 - 50.000")
            print("aborting..")
            exit()
        self.port_ping = self.starting_port
        self.port_game_start = self.starting_port + 1
        self.port_game_end = self.starting_port + self.number_of_slaves
        self.port_voice_start = self.starting_port + self.number_of_slaves + 1
        self.port_voice_end = self.starting_port + ( self.number_of_slaves * 2 )

        self.prepare_config("port_ping", self.port_ping - 10000)
        self.prepare_config("port_game_start", self.port_game_start - 10000)
        self.prepare_config("port_game_end", self.port_game_end - 10000)
        self.prepare_config("port_voice_start", self.port_voice_start - 10000)
        self.prepare_config("port_voice_end", self.port_voice_end - 10000)
        self.prepare_config("port_proxy_start", self.port_ping)
        self.prepare_config("port_proxy_end", self.port_voice_end)

    def make_commands(self):
        #TODO: this is kinda ugly. it works, but i need to find a better way
        list_of_cores = []
        for i in range(self.max_cpu):
            list_of_cores.append(str(i))
        parameters = [
            f"Set man_masterLogin {self.username}:",
            f"Set man_masterPassword {self.password}",
            f"Set man_numSlaveAccounts {self.number_of_slaves}",
            f"Set man_startServerPort {self.port_game_start - 10000}",
            f"Set man_endServerPort {self.port_game_end - 10000}",
            f"Set man_voiceProxyStartPort {self.port_voice_start - 10000}",
            f"Set man_voiceProxyEndPort {self.port_voice_end - 10000}",
            f"Set man_maxServers {self.number_of_slaves}",
            f"Set man_enableProxy true",
            f"Set host_affinity -1",
            f"Set man_broadcastSlaves true",
            f"Set man_autoServersPerCPU {self.servers_per_core}",
            f"Set man_allowCPUs {','.join(list_of_cores)}",
            f"Set man_uploadToS3OnDemand 1",
            f"Set man_uploadToCDNOnDemand 0",
            f"Set svr_name {self.server_name} 0",
            f"Set svr_location {self.region}",
            f"Set svr_ip {self.ip}",
            f"Set svr_port {self.port_ping}",
        ]
        self.prepare_config("commands", ';'.join(parameters))

    def make_proxy_conf(self):
        parameters = [
            f"count={self.number_of_slaves}",
            f"ip={self.ip}",
            f"startport={self.port_game_start - 10000}",
            f"startvoiceport={self.port_voice_start - 10000}",
            f"proxy_region=naeu",
        ]
        for item in parameters:
            key, value = item.split("=")
            self.prepare_config(key, value)

    def do_auto_config(self):
        self.calculate_ports()
        self.prepare_config("ip", self.ip)
        self.make_commands()
        self.make_proxy_conf()


instance = configGenerator()
instance.do_auto_config()
