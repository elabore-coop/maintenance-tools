from odoo import fields, models, api


class ProjectTask(models.Model):
    _inherit = "project.task"

    maintenance_request_ids = fields.One2many("maintenance.request", "task_id", string="Maintenance Requests")
    maintenance_request_count = fields.Integer(
        compute="_compute_maintenance_request_count"
    )

    @api.depends("maintenance_request_ids")
    def _compute_maintenance_request_count(self):
        for task in self:
            task.maintenance_request_count = len(
                task.maintenance_request_ids.filtered(lambda x: not x.stage_id.done)
            )

    def action_view_maintenance_request_ids(self):
        """
        Access to the undone maintenance requests for this task
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "maintenance.hr_equipment_request_action"
        )
        action["domain"] = [("task_id", "=", self.id), ("stage_id.done", "=", False)]
        action["context"] = {"default_task_id": self.id}
        return action
