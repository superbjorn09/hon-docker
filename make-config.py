#!/usr/bin/env python3
import requests
import configparser
import multiprocessing
from os.path import isfile

first_run = '''
--- INFO ---

1. Getting Started
----------------------------------------------------------
It seems that you re running this script for the first time! Follow the below steps to get started.

Right now a template file is created in your source directory called .env
Edit it using your editor of choice (nano, vim etc) and fill in the variables in these sections:
- credentials
- network
- server
- optional.
After you have done this, run ./make-config.py once more.
The auto-section in the .env file will now populate with the proper information.

2. How The Networking Works
----------------------------------------------------------
Port numbers are calculated like this:
Number of ports = starting_port * 2 + 1

Each server instance needs 1 game and 1 voice port. One additional port is used as ping port,
so your instances can be found by auto-region. If you re just testing, set the region to NEWERTH
and do not forward the first port in your router. This way, you can test your config and make
sure that the server is running like it's supposed to, since doing it this way, only exposes
the server to public games.

Setting it to a specific region (like EU) will make it available for that region. If you were
to forward the ping port in your router the server would become available for TMM regardless
of which region you've chosen, since the latency is the only prerequisite for exposing your
server for TMM's.

3. Optional: use_metricbeat
----------------------------------------------------------
On the first run the script will generate client certificates for the stats website made by Frank.
You will be asked to provide the generated Certificate Signing Request -- client.csr
Send it to him via Discord: https://discordapp.com/users/197967989964800000

Frank will then send the client.pem back to you, which belongs to your specific docker container. 
You will then have to manually put the client.pem inside of your docker containers specified volume.

The docker volume can be found by running: sudo docker inspect kongor_online | grep volume
Your certificates are stored in the filebeat volume.

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
        print("Adjust the values in .env and run the script again.")
        exit()


    def prepare_config(self, key, value):
        self.config.set("auto", str(key), str(value))
        self.write_config()

    def write_config(self):
        with open(self.config_filename, "w") as f:
            self.config.write(f, space_around_delimiters=False)

    def calculate_ports(self):
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
