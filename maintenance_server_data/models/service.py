from odoo import fields, models

class Service(models.Model):
    _name = 'service'

    name = fields.Char('Name', required=True)
    
class ServiceVersion(models.Model):
    _name = "service.version"

    service_id = fields.Many2one('service', string='Service', required=True)
    name = fields.Char('Name')
    is_last_version = fields.Boolean('Is Last Version?')

class ServiceInstance(models.Model):
    _name = "service.instance"

    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment')
    service_id = fields.Many2one('service', string='Service', required=True)
    version_id = fields.Many2one('service.version', string='Version')
    service_url = fields.Char(string='Service Url')


class BackupServer(models.Model):
    _name = 'backup.server'

    name = fields.Char('Name', required=True)