from odoo import api, fields, models

class OsDistribution(models.Model):
    _name = 'os.distribution'

    name = fields.Char('Name', compute="_compute_name")
    distrib_name = fields.Char('Distrib Name', required=True)
    distrib_version = fields.Char('Distrib Version')

    @api.depends("distrib_name","distrib_version")
    def _compute_name(self):
        for distrib in self:
            distrib.name = ""
            if distrib.distrib_name != "":
                distrib.name = distrib.distrib_name
            if distrib.distrib_version != "":
                distrib.name = distrib.name + ' ' + distrib.distrib_version