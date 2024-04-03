from odoo import fields, models, api
import subprocess
import sys
import psutil
from io import StringIO

AVAILABLE_MEMORY_PERCENT_COMMAND = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
MIN_AVAILABLE_MEMORY_PERCENT_WARNING = 20
MIN_AVAILABLE_MEMORY_PERCENT_ERROR = 5

USED_DISK_SPACE_COMMAND = "df /srv -h | tail -n +2 | sed -r 's/ +/ /g' | cut -f 5 -d ' ' | cut -f 1 -d %"
MAX_USED_DISK_SPACE_WARNING = 70
MAX_USED_DISK_SPACE_ERROR = 90

MAX_PING_MS_WARNING = 1000
MAX_PING_MS_ERROR = 5000


"""
if you want to add a new test : 
    * add new field to MaintenanceEquipment (named {fieldname} below)
    * add a new function named test_{fieldname} which return a filled MonitoringTest class with :
        -> log = logs you want to appear in logs
        -> result = value which will be set to {fieldname}
        -> error = MonitoringTest.ERROR or MonitoringTest.WARNING to generate maintenance request
    * add requirements if necessary in install_dependencies function
    * call your function in monitoring_test() with a simple launch_test({fieldname}, *args)
        if needed, *args can be passed by parameters to your test function


"""


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'
    
    last_monitoring_test_date = fields.Datetime('Date of last monitoring test', readonly=True)
    ping_ok = fields.Boolean("Ping ok", readonly=True)
    available_memory_percent = fields.Float('Percent of available memory', readonly=True)
    used_disk_space = fields.Float('Percent of used disk space', readonly=True)
    log = fields.Html("Log", readonly=True)
    error_maintenance_request = fields.Many2one('maintenance.request', "Error maintenance request")
    warning_maintenance_request = fields.Many2one('maintenance.request', "Warning maintenance request")


    class MonitoringTest:        
        """Class to make the tests
        """
        WARNING = "warning"
        ERROR = "error"

        def __init__(self, name):
            self.name = name #name of the test
            self.result = 0 #result of the test
            self.log = "" #logs of the test
            self.date = fields.Datetime.now() #date of the test
            self.error = "" #errors of the test

        def add_to_log(self, text):   
            """
                add a new line to logs composed with DATE > TEST NAME > WHAT TO LOG
            """     
            self.log += f"{self.date} > {self.name} > {text}\n"
        
    @api.model
    def cron_monitoring_test(self):
        """cron launch test on all equipments
        """
        self.search([]).monitoring_test()
    
    def monitoring_test(self):    

        def launch_test(attribute, *test_function_args):
            """run test function with name = test_[attribute]
            associate result of test to equipment
            write logs of test


            Args:
                attribute (string): attribute of MaintenanceEquipment we want to test

            Returns:
                MonitoringTest: returned by test function
            """
            test_function = getattr(equipment,"test_"+attribute)
            test = test_function(*test_function_args)            
            setattr(equipment, attribute, test.result)
            log.write(test.log)            
            tests.append(test)
            return test


        for equipment in self:
            #clear log            
            log = StringIO() #we use StingIO instead of string to use mutable object 

            tests = []

            #install dependencies and log it
            log.write(equipment.install_dependencies().log) # launch_test is not used, only logs are necessary

            #run ping test
            launch_test("ping_ok")

            #SSH dependant test
            try:
                ssh = self.get_ssh_connection() #ssh connection given by maintenance_server_ssh module
            except Exception as e:
                ssh = False
                log.write(f"{fields.Datetime.now()} > SSH > connection failed {e}\n")
                
            
            if ssh:
                #test available memory
                launch_test("available_memory_percent", ssh)         

                #test disk usage
                launch_test("used_disk_space", ssh)
            else:
                equipment.available_memory_percent = -1 #set -1 by convention if error
                equipment.used_disk_space = -1 #set -1 by convention if error         

            #set test date
            equipment.last_monitoring_test_date = fields.Datetime.now()
            
            #write logs
            log.seek(0) #log is a StringIO so seek to beginning before read
            new_log = f'📣 {fields.Datetime.now()}\n{log.read()}\n'   
            new_log = new_log.replace("\n","<br />") # log field is HTML, so format lines 
            equipment.log = f'{new_log}<br />{equipment.log}'[:10000] #limit logs to 10000 characters

            #if error create maintenance request
            error = warning =False
            if any(test.error == test.ERROR for test in tests):
                error = True # if any arror in tests
            elif any(test.error == test.WARNING for test in tests):
                warning = True # if any warning in tests

            if error or warning:                
                # check if error or warning request already exists before creating a new one
                # if only a warning exists, error request will be created anyway
                if (error and not equipment.error_maintenance_request) \
                    or (warning and not equipment.warning_maintenance_request and not equipment.error_maintenance_request):
                    maintenance_request = self.env['maintenance.request'].create({
                        "name":f'[{"ERROR" if error else "WARNING"}] {equipment.name}',
                        "equipment_id":equipment.id, 
                        "employee_id":equipment.employee_id,
                        "user_id":equipment.technician_user_id,
                        "maintenance_team_id":equipment.maintenance_team_id.id or self.env["maintenance.team"].search([], limit=1),
                        "priority":'2' if error else '3',
                        "maintenance_type":"corrective" if error else "preventive", 
                        "description":new_log
                    })
                    if error:
                        equipment.error_maintenance_request = maintenance_request
                    else:
                        equipment.warning_maintenance_request = maintenance_request
                

    
    def install_dependencies(self):
        """
            install dependencies needed to do all tests, as python or shell programs

            Returns:
                MonitoringTest: representing current test with result=0 if not error
        """        
        monitoring_test = self.MonitoringTest("install dependencies")
        if "ping3" in sys.modules:
            monitoring_test.add_to_log("ping3 already satisfied")
            monitoring_test.result = 0
        else:
            error = True
            try:
                command = ['pip','install',"ping3"]
                response = subprocess.call(command) # run "pip install ping3" command
                if response == 0:
                    error = False
            except Exception as e:
                error = str(e)
                
            if error:
                monitoring_test.add_to_log(f"🚨 ping3 : unable to install : {error}")
                monitoring_test.result = -1
                monitoring_test.error = monitoring_test.ERROR
            else:
                monitoring_test.add_to_log("ping3 installation successful")
                monitoring_test.result = 0
        
        return monitoring_test
    
    
    def test_available_memory_percent(self, ssh):    
        """
            test available memory with a bash command called by ssh

            Args:
                ssh (paramiko.SSHClient): ssh client

            Returns:
                MonitoringTest: representing current test with :
                    * result = -2 if error
                    * result = percent of available memory if no error
                    * error defined with ERROR or WARNING depending on result comparaison 
                        with MIN_AVAILABLE_MEMORY_PERCENT_WARNING and MIN_AVAILABLE_MEMORY_PERCENT_ERROR
                    * log file
        """      
        try:      
            test = self.MonitoringTest("Available memory percent")      
            _stdin, stdout, _stderr = ssh.exec_command(AVAILABLE_MEMORY_PERCENT_COMMAND)
            test.result = float(stdout.read().decode())
            if test.result > MIN_AVAILABLE_MEMORY_PERCENT_WARNING:
                test.add_to_log(f"OK : {test.result}% available")
            elif test.result > MIN_AVAILABLE_MEMORY_PERCENT_ERROR: #memory between warning and error step
                test.add_to_log(f"🔥 WARNING : {test.result}% available")
                test.error = test.WARNING                
            else:
                test.add_to_log(f"🚨 ERROR : {test.result}% available") #memory available lower than error step
                test.error = test.ERROR
        except Exception as e:
            test.result = -2
            test.add_to_log(f"🚨 ERROR : {e}")
        return test

        
    def test_used_disk_space(self, ssh):        
        """
            test Used disk space with a bash command called by ssh

            Args:
                ssh (paramiko.SSHClient): ssh client

            Returns:
                MonitoringTest: representing current test with :
                    * result = -2 if error
                    * result = percent of Used disk space if no error
                    * error defined with ERROR or WARNING depending on result comparaison 
                        with MAX_USED_DISK_SPACE_WARNING and MAX_USED_DISK_SPACE_ERROR
                    * log file
        """      
        try:
            test = self.MonitoringTest("Used disk space")      
            _stdin, stdout, _stderr = ssh.exec_command(USED_DISK_SPACE_COMMAND)
            test.result = float(stdout.read().decode())                    
            if test.result < MAX_USED_DISK_SPACE_WARNING:
                test.add_to_log(f"OK : {test.result}% used")
            elif test.result < MAX_USED_DISK_SPACE_ERROR:
                test.add_to_log(f"🔥 WARNING : {test.result}% used") # disk usage between WARNING and ERROR steps
                test.error = test.WARNING
            else:
                test.add_to_log(f"🚨 ERROR : {test.result}% used") # disk usage higher than ERROR steps
                test.error = test.ERROR
                
        except Exception as e:
            test.result = -2
            test.add_to_log(f"🚨 ERROR : {e}")            
        return test
        
    
    def test_ping_ok(self):
        """
            test PING with ping3 library

            Returns:
                MonitoringTest: representing current test with :
                    * result = False if error
                    * result = True if no error
                    * error defined with ERROR or WARNING depending on ping time comparaison 
                        with MAX_PING_MS_WARNING and MAX_PING_MS_ERROR
                    * log file
        """   
        test = self.MonitoringTest("Ping")
        try:               
            from ping3 import ping
        except Exception as e:            
            test.result = False
            test.add_to_log(f"🚨 ping3 dependencie not satisfied : {e}")
            test.error = test.ERROR
            return
        
        hostname = self.server_domain
        try:
            r = ping(hostname)
        except Exception as e: 
            test.result = False
            test.error = test.ERROR
            test.add_to_log(f"🚨 unable to call ping ! > {e}")  
        if r:
            test.result = True
            ping_ms = int(r*1000)
            if ping_ms < MAX_PING_MS_WARNING:
                test.add_to_log("PING OK in "+str(ping_ms)+"ms")
            elif ping_ms < MAX_PING_MS_ERROR:
                test.add_to_log("🔥 WARNING : PING OK in "+str(ping_ms)+"ms")            
                test.error = test.WARNING
            else:
                test.add_to_log("🚨 ERROR : PING OK in "+str(ping_ms)+"ms")
                test.error = test.ERROR
        else:   
            test.result = False
            test.error = test.ERROR
            test.add_to_log("🚨 PING FAILED")        
        return test