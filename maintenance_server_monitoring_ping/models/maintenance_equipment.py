from odoo import fields, models, api
import subprocess

MAX_PING_MS_WARNING = 1000
MAX_PING_MS_ERROR = 5000

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'    
    
    ping_ok = fields.Boolean("Ping ok", readonly=True)
         
    def get_tests(self):
        res = super(MaintenanceEquipment, self).get_tests()
        res.append("ping_ok")
        return res
    
    def test_ping_ok(self):
        """
            test PING with ping3 library

            Returns:
                MonitoringTest: representing current test with :
                    * result = False if error
                    * result = True if no error
                    * error defined with MonitoringTest.ERROR or MonitoringTest.WARNING depending on ping time comparaison 
                        with MAX_PING_MS_WARNING and MAX_PING_MS_ERROR
                    * log file
        """   
        test = self.MonitoringTest("Ping")    

        try:               
            from ping3 import ping
        except ImportError as e:
            # unable to import ping3
            try:                
                command = ['pip3','install',"ping3==4.0.5"]
                response = subprocess.call(command) # run "pip install ping3" command
                if response != 0:                    
                    return test.test_error(False, f"ping3 : unable to install : response = {response}")          
                else:
                    from ping3 import ping
            except Exception as e:                
                return test.test_error(False, f"ping3 : unable to install : {e}")
        
        hostname = self.server_domain
        if not hostname:
            # equipment host name not filled 
            return test.test_error(False, f"host name seems empty !")             

        try:
            r = ping(hostname)
        except Exception as e: 
            # Any problem when call ping
            return test.test_error(False, f"unable to call ping ! > {e}")             
           
        if r:
            test.result = True
            ping_ms = int(r*1000)
            if ping_ms < MAX_PING_MS_WARNING:     
                # ping OK           
                return test.test_ok(True, f"PING OK in {ping_ms} ms")             
            elif ping_ms < MAX_PING_MS_ERROR:                
                # ping result between WARNING and ERROR => WARNING
                return test.test_warning(True, f"PING OK in {ping_ms}ms (> {MAX_PING_MS_WARNING})")             
            else:
                # ping result higher than ERROR => ERROR
                return test.test_error(True, f"PING OK in {ping_ms}ms (> {MAX_PING_MS_ERROR})")                             
        else:  
            return test.test_error(False, "PING FAILED")                              
            
        