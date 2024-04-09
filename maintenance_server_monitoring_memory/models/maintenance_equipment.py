from odoo import fields, models, api


AVAILABLE_MEMORY_PERCENT_COMMAND = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
MIN_AVAILABLE_MEMORY_PERCENT_WARNING = 20
MIN_AVAILABLE_MEMORY_PERCENT_ERROR = 5

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'    
    
    available_memory_percent = fields.Float('Percent of available memory', readonly=True)
         
    def get_tests(self):
        res = super(MaintenanceEquipment, self).get_tests()
        res.append("available_memory_percent")
        return res
    
    def test_available_memory_percent(self):    
        """
            test available memory with a bash command called by ssh

            Args:
                ssh (paramiko.SSHClient): ssh client

            Returns:
                MonitoringTest: representing current test with :
                    * result = -2 if error
                    * result = percent of available memory if no error
                    * error defined with MonitoringTest.ERROR or MonitoringTest.WARNING depending on result comparaison 
                        with MIN_AVAILABLE_MEMORY_PERCENT_WARNING and MIN_AVAILABLE_MEMORY_PERCENT_ERROR
                    * log file
        """      
        test = self.MonitoringTest("Available memory percent")      
        try:
            ssh = self.get_ssh_connection()
            if not ssh:
                return test.test_error(-2, "No ssh connection")            
            _stdin, stdout, _stderr = ssh.exec_command(AVAILABLE_MEMORY_PERCENT_COMMAND)
            available_memory_percent = float(stdout.read().decode())
            if available_memory_percent > MIN_AVAILABLE_MEMORY_PERCENT_WARNING:                
                return test.test_ok(available_memory_percent, f"{available_memory_percent}% available")
            elif available_memory_percent > MIN_AVAILABLE_MEMORY_PERCENT_ERROR: 
                # memory between warning and error step
                return test.test_warning(available_memory_percent, f"{available_memory_percent}% available (<{MIN_AVAILABLE_MEMORY_PERCENT_WARNING})")                
            else:
                # memory available lower than error step
                return test.test_error(available_memory_percent, f"{available_memory_percent}% available (<{MIN_AVAILABLE_MEMORY_PERCENT_ERROR})")
        except Exception as e:
            return test.test_error(-2, f"{e}")                         
            
        