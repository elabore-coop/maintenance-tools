from odoo import fields, models
import subprocess
import sys
import psutil


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    server_domain = fields.Char('Server Domain')    
    ssh_private_key_path = fields.Char("SSH private key path", default="/opt/odoo/auto/dev/ssh_keys/id_rsa")
            
    def get_ssh_connection(self):      
        ssh_connections = self.env.context.get('ssh_connections',{})
        if self.id in ssh_connections:
            return ssh_connections[self.id]

        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.server_domain, username="root", key_filename=self.ssh_private_key_path)        

        ssh_connections[self.id] = ssh
        self = self.with_context(ssh_connections=ssh_connections)
        return ssh
    
    