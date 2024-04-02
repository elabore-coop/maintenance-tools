from odoo import fields, models
import subprocess
import sys
import psutil


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    server_domain = fields.Char('Server Domain')    
    ssh_private_key_path = fields.Char("SSH private key path", default="/opt/odoo/auto/dev/ssh_keys/id_rsa")
    last_monitoring_test_date = fields.Datetime('Date of last monitoring test', readonly=True)
    ping_ok = fields.Boolean("Ping ok", readonly=True)
    available_memory_percent = fields.Float('Percent of available memory', readonly=True)

    def install_dependencies(self):
        if "ping3" not in sys.modules:
            command = ['pip','install',"ping3"]
            response = subprocess.call(command)
            return response
    

    def monitoring_test(self):
        self.install_dependencies()
        self.test_ping()
        self.test_available_memory_percent()
        self.last_monitoring_test_date = fields.Datetime.now()
        return
    
    def test_available_memory_percent(self):
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.server_domain, username="root", key_filename=self.ssh_private_key_path)
        _stdin, stdout, _stderr = ssh.exec_command("free | grep Mem | awk '{print $3/$2 * 100.0}'")
        self.available_memory_percent = float(stdout.read().decode())        
    
    def test_ping(self):                
        from ping3 import ping
        hostname = self.server_domain
        r = ping(hostname)
        if r:
            self.ping_ok = True
        else:   
            self.ping_ok = False
        return