from odoo import fields, models, api
import subprocess
import sys
import psutil
from io import StringIO

LOG_LIMIT = 100000



"""
if you want to add a new test : 
    * create new module named maintenance_server_monitoring_{your_test}
    * add new field to MaintenanceEquipment (named {fieldname} below)
    * add a new function named test_{fieldname} which return a filled MonitoringTest class with :
        -> log = logs you want to appear in logs
        -> result = value which will be set to {fieldname}
        -> error = MonitoringTest.ERROR or MonitoringTest.WARNING to generate maintenance request
        ** Note you can use test_ok, test_warning, and test_error functions to simplify code **
    * inherit get_tests() to reference your field {fieldname}

be inspired by maintenance_server_monitoring_ping for exemple
"""


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'
    
    last_monitoring_test_date = fields.Datetime('Date of last monitoring test', readonly=True)

    enable_monitoring = fields.Boolean('Monitoring enabled', help="If enabled, cron will test this equipment")

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

    def launch_test(self, field_name, *test_function_args):
            """run test function with name = test_[attribute]
            associate result of test to equipment
            write logs of test


            Args:
                attribute_name (string): attribute of MaintenanceEquipment we want to test
                *test_function_args = optionnal args to pass to function (unused for the moment)

            Returns:
                MonitoringTest: returned by test function
            """
            test_function = getattr(self,"test_"+field_name)
            test = test_function(*test_function_args)            
            setattr(self, field_name, test.result)            
            return test
    
    def get_tests(self):
        """function to inherit in sub-modules        

        Returns:
            array[string]: names of fields to test
        """
        return []
    
    def monitoring_test(self):    

        for equipment in self:                        
            # array of all tests
            tests_results = []

            # run all tests referenced in get_tests and save result
            for test in self.get_tests():
                tests_results.append(equipment.launch_test(test))

            # set test date
            equipment.last_monitoring_test_date = fields.Datetime.now()
            
            # write logs
            #new logs are current datetime + join of test results logs
            new_log = f'📣 {fields.Datetime.now()}\n{"".join([tests_result.log for tests_result in tests_results])}\n'.replace("\n","<br />")
            #add new logs to the beginning of equipment log
            equipment.log = f'{new_log}<br />{equipment.log}'[:LOG_LIMIT] #limit logs 

            #Create maintenance request only if monitoring is enabled
            if not equipment.enable_monitoring:
                return

            # if error create maintenance request
            error = warning =False
            if any(test.error == test.ERROR for test in tests_results):
                error = True # if any arror in tests
            elif any(test.error == test.WARNING for test in tests_results):
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
                    equipment.create_maintenance_request(self.MonitoringTest.ERROR if error else self.MonitoringTest.WARNING, new_log)            
            else:                
                equipment.no_error()


    def create_maintenance_request(self, error_level, description):
        """create a maintenance request for equipment (self)

        Args:
            error_level (string): MonitoringTest.ERROR or MonitoringTest.WARNING
            description (string): description of maintenance request
        """
        maintenance_request = self.env['maintenance.request'].create({
            "name":f'[{error_level.upper()}] {self.name}',
            "equipment_id":self.id,                         
            "user_id":self.technician_user_id.id,
            "maintenance_team_id":self.maintenance_team_id.id or self.env["maintenance.team"].search([], limit=1),
            "priority":'2' if error_level == self.MonitoringTest.ERROR else '3',
            "maintenance_type":"corrective" if error_level == self.MonitoringTest.ERROR else "preventive", 
            "description":description
        })
        if error_level == self.MonitoringTest.ERROR:
            self.error_maintenance_request = maintenance_request
            self.warning_maintenance_request = None
        else:
            self.warning_maintenance_request = maintenance_request
            self.error_maintenance_request = None    
    
    def no_error(self):
        """set error and warning maintenance request to None
        """
        self.error_maintenance_request = None
        self.warning_maintenance_request = None
        
            
    
            
    
                 
    
    
    