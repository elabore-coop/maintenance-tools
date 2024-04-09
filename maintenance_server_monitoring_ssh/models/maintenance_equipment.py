from odoo import fields, models, api

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'    
        
    ssh_ok = fields.Boolean("SSH ok", readonly=True)
         
    def get_tests(self):
        res = super(MaintenanceEquipment, self).get_tests()
        res.append("ssh_ok")
        return res
    
    def test_ssh_ok(self):    
        """
            test ssh with maintenance_server_ssh module

            Returns:
                MonitoringTest: representing current test with :
                    * result = False if error
                    * result = ssh connection if no error
                    * error = MonitoringTest.ERROR if connection failed
                    * log file
        """   
        test = self.MonitoringTest("SSH OK")    
        self.get_ssh_connection()
        try:
            # SSH connection ok : set ssh connection in result, converted in boolean (True) when set in ssh_ok field
            return test.test_ok(self.get_ssh_connection(), "SSH Connection OK") #ssh connection given by maintenance_server_ssh module            
        except Exception as e:
            # SSH connection failed
            return test.test_error(False, "connection failed {e}")