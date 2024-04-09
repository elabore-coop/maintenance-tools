from odoo import fields, models, api


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'    
    
    def create_maintenance_request(self, error_level, description):
        res = super(MaintenanceEquipment, self).create_maintenance_request(error_level, description)
        if self.error_maintenance_request:
            error_status = self.env["maintenance.equipment.status"].search([("is_error_status",'=',True),'|', ('category_ids', 'in', [self.category_id.id]), ('category_ids', '=', False)])
            if error_status:
                self.status_id = error_status
        else:
            warning_status = self.env["maintenance.equipment.status"].search([("is_warning_status",'=',True),'|', ('category_ids', 'in', [self.category_id.id]), ('category_ids', '=', False)])
            if warning_status:
                self.status_id = warning_status
        return res

    def no_error(self):
        res = super(MaintenanceEquipment, self).no_error()
        ok_status = self.env["maintenance.equipment.status"].search([("is_error_status",'=',False),("is_warning_status",'=',False),'|', ('category_ids', 'in', [self.category_id.id]), ('category_ids', '=', False)])
        self.status_id = ok_status
        return res
