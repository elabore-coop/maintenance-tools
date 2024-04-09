from odoo import fields, models, api
import subprocess
import sys
import psutil
from io import StringIO

class MaintenanceEquipmentStatus(models.Model):
    _inherit = "maintenance.equipment.status"
    
    is_warning_status = fields.Boolean('Is warning status')
    is_error_status = fields.Boolean('Is error status')