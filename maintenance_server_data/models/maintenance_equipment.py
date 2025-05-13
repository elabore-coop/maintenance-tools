from odoo import fields, models, api


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    server_ip = fields.Char("Server Ip Address")
    distribution_id = fields.Many2one("os.distribution", string="Distribution")
    service_ids = fields.One2many("service.instance", "equipment_id", string="Services")
    hosting_city = fields.Char("Hosting City")
    nb_cores = fields.Integer("Nb Cores")
    ram = fields.Integer("RAM (Go)")
    disk_storage = fields.Integer("Disk Storage (Go)")
    backup_activated = fields.Boolean("Backup Activated ?")
    backup_server_id = fields.Many2one("backup.server", string="Backup Server")
    backup_ok = fields.Boolean("Backup OK ?")

    name_fr = fields.Char("Name (FR)", compute="_compute_name_fr", store=True)

    @api.depends("name")
    def _compute_name_fr(self):
        for record in self:
            record.name_fr = record.with_context(lang="fr_FR").name
