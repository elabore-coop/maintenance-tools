from odoo import fields, models, api
import subprocess
import sys
import psutil
from io import StringIO

LOG_LIMIT = 100000

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
        ** Note you can use test_ok, test_warning, and test_error functions to simplify code **
    * add requirements if necessary in install_dependencies function
    * call your function in monitoring_test() with a simple launch_test({fieldname}, *args)
        if needed, *args can be passed by parameters to your test function


"""


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'
    
    last_monitoring_test_date = fields.Datetime('Date of last monitoring test', readonly=True)

    enable_monitoring = fields.Boolean('Monitoring enabled', help="If enabled, cron will test this equipment")

    #tests
    ping_ok = fields.Boolean("Ping ok", readonly=True)
    available_memory_percent = fields.Float('Percent of available memory', readonly=True)
    used_disk_space = fields.Float('Percent of used disk space', readonly=True)
    ssh_ok = fields.Boolean("SSH ok", readonly=True)

    #log
    log = fields.Html("Log", readonly=True)

    #maintenance requests
    error_maintenance_request = fields.Many2one('maintenance.request', "Error maintenance request")
    warning_maintenance_request = fields.Many2one('maintenance.request', "Warning maintenance request")


    class MonitoringTest:        
        """Class to make the tests
        """
        WARNING = "warning"
        ERROR = "error"

        def __init__(self, name):
            self.name = name # name of the test
            self.result = 0 # result of the test
            self.log = "" # logs of the test
            self.date = fields.Datetime.now() # date of the test
            self.error = "" # errors of the test

        def add_to_log(self, text):   
            """
                add a new line to logs composed with DATE > TEST NAME > WHAT TO LOG
            """     
            self.log += f"{self.date} > {self.name} > {text}\n"

        def test_ok(self, result, log):
            """to call when the test is ok.
            It just fill the test with result and embellished log

            Args:
                result: result of test
                log (string): what to log

            Returns:
                MonitoringTest: filled test
            """
            self.add_to_log(log)
            self.result = result
            return self
        
        def test_error(self, result, log):
            """to call when test error.
            It just fill the test with result, embellished log and set error value to ERROR

            Args:
                result: result of test
                log (string): what to log

            Returns:
                MonitoringTest: filled test
            """
            self.add_to_log(f"🚨 ERROR : {log}")
            self.result = result
            self.error = self.ERROR
            return self
        
        def test_warning(self, result, log):
            """to call when test warning.
            It just fill the test with result, embellished log and set error value to WARNING

            Args:
                result: result of test
                log (string): what to log

            Returns:
                MonitoringTest: filled test
            """
            self.add_to_log(f"🔥 WARNING : {log}")
            self.result = result
            self.error = self.WARNING
            return self
        
    @api.model
    def cron_monitoring_test(self):
        """cron launch test on all equipments
        """
        self.search([("enable_monitoring","=",True)]).monitoring_test()
    
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
            
            # we use StingIO instead of string to use mutable object 
            log = StringIO() 

            # array of all tests
            tests = []

            # install dependencies and log it
            log.write(equipment.install_dependencies().log) # launch_test is not used, only logs are necessary

            # run ping test
            launch_test("ping_ok")

            # SSH dependant test
            ssh = launch_test("ssh_ok").result
                
            
            if ssh:
                # test available memory
                launch_test("available_memory_percent", ssh)         

                # test disk usage
                launch_test("used_disk_space", ssh)
            else:
                equipment.available_memory_percent = -1 #set -1 by convention if error
                equipment.used_disk_space = -1 #set -1 by convention if error         

            # set test date
            equipment.last_monitoring_test_date = fields.Datetime.now()
            
            # write logs
            log.seek(0) #log is a StringIO so seek to beginning before read
            new_log = f'📣 {fields.Datetime.now()}\n{log.read()}\n'   
            new_log = new_log.replace("\n","<br />") # log field is HTML, so format lines 
            equipment.log = f'{new_log}<br />{equipment.log}'[:LOG_LIMIT] #limit logs 

            #Create maintenance request only if monitoring is enabled
            if not equipment.enable_monitoring:
                return

            # if error create maintenance request
            error = warning =False
            if any(test.error == test.ERROR for test in tests):
                error = True # if any arror in tests
            elif any(test.error == test.WARNING for test in tests):
                warning = True # if any warning in tests

            if error or warning:                
                # check if error or warning request (not done) already exists before creating a new one
                # if only a warning request exists, error request will be created anyway
                existing_not_done_error_request = None
                existing_not_done_warning_request = None
                if equipment.error_maintenance_request and not equipment.error_maintenance_request.stage_id.done:
                    existing_not_done_error_request = equipment.error_maintenance_request
                if equipment.warning_maintenance_request and not equipment.warning_maintenance_request.stage_id.done:
                    existing_not_done_warning_request = equipment.warning_maintenance_request
                if (error and not existing_not_done_error_request) \
                    or (warning and not existing_not_done_warning_request and not existing_not_done_error_request):
                    maintenance_request = self.env['maintenance.request'].create({
                        "name":f'[{"ERROR" if error else "WARNING"}] {equipment.name}',
                        "equipment_id":equipment.id,                         
                        "user_id":equipment.technician_user_id.id,
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
        try:
            import ping3
            return monitoring_test.test_ok(0, "ping3 already installed")            
        except ImportError:        
            try:                
                command = ['pip3','install',"ping3==4.0.5"]
                response = subprocess.call(command) # run "pip install ping3" command
                if response == 0:
                    return monitoring_test.test_ok(0, "ping3 installation successful")  
                else:
                    monitoring_test.test_error(f"ping3 : unable to install : response = {response}")          
            except Exception as e:                
                return monitoring_test.test_error(f"ping3 : unable to install : {e}")
            
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
        try:
            # SSH connection ok : set ssh connection in result, converted in boolean (True) when set in ssh_ok field
            return test.test_ok(self.get_ssh_connection(), "SSH Connection OK") #ssh connection given by maintenance_server_ssh module            
        except Exception as e:
            # SSH connection failed
            return test.test_error(False, f"{fields.Datetime.now()} > SSH > connection failed {e}\n")
            
    
    def test_available_memory_percent(self, ssh):    
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
        try:      
            test = self.MonitoringTest("Available memory percent")      
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
        

        
    def test_used_disk_space(self, ssh):        
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
        try:
            test = self.MonitoringTest("Used disk space")      
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
        except Exception as e:
            # unable to import ping3
            return test.test_error(False, f"ping3 dependencie not satisfied : {e}")               
        
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
                return test.test_error(False, f"PING OK in {ping_ms}ms (> {MAX_PING_MS_ERROR})")                             
        else:  
            return test.test_error(False, "PING FAILED")                              
            
        