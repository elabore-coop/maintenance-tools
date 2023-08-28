from odoo import fields, models



class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    server_ip = fields.Char('Server Ip Address')
    distribution_id = fields.Many2one('os.distribution', string='Distribution')
    service_ids = fields.One2many('service.instance', 'equipment_id', string='Services')
    hosting_city = fields.Char('Hosting City')
    nb_cores = fields.Integer('Nb Cores')
    ram = fields.Integer('RAM (Go)')
    disk_storage = fields.Integer('Disk Storage (Go)')
    backup_activated = fields.Boolean('Backup Activated ?')
    backup_server_id = fields.Many2one('backup.server', string='Backup Server')
    backup_ok = fields.Boolean('Backup OK ?')