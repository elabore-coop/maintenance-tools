from odoo import fields, models, api

USED_DISK_SPACE_COMMAND = "df /srv -h | tail -n +2 | sed -r 's/ +/ /g' | cut -f 5 -d ' ' | cut -f 1 -d %"
MAX_USED_DISK_SPACE_WARNING = 70
MAX_USED_DISK_SPACE_ERROR = 90


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'    
        
    used_disk_space = fields.Float('Percent of used disk space', readonly=True)
         
    def get_tests(self):
        res = super(MaintenanceEquipment, self).get_tests()
        res.append("used_disk_space")
        return res
    
    def test_used_disk_space(self):        
        """
            test Used disk space with a bash command called by ssh

            Args:
                ssh (paramiko.SSHClient): ssh client

            Returns:
                MonitoringTest: representing current test with :
                    * result = -2 if error
                    * result = percent of Used disk space if no error
                    * error defined with MonitoringTest.ERROR or MonitoringTest.WARNING depending on result comparaison 
                        with MAX_USED_DISK_SPACE_WARNING and MAX_USED_DISK_SPACE_ERROR
                    * log file
        """      
        test = self.MonitoringTest("Used disk space")      
        try:
            ssh = self.get_ssh_connection()
            if not ssh:
                return test.test_error(-2, "No ssh connection")            
            _stdin, stdout, _stderr = ssh.exec_command(USED_DISK_SPACE_COMMAND)
            used_disk_space = float(stdout.read().decode())                    
            if used_disk_space < MAX_USED_DISK_SPACE_WARNING:
                return test.test_ok(used_disk_space, f"{used_disk_space}% used")                
            elif used_disk_space < MAX_USED_DISK_SPACE_ERROR:
                # disk usage between WARNING and ERROR steps
                return test.test_warning(used_disk_space, f"{used_disk_space}% used (>{MAX_USED_DISK_SPACE_WARNING})")                
            else:
                # disk usage higher than ERROR steps
                return test.test_error(used_disk_space, f"{used_disk_space}% used (>{MAX_USED_DISK_SPACE_ERROR})")                
                                
        except Exception as e:
            return test.test_error(-2, f"{e}")                   
            
        