from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval

class CreateMaintenanceRequestsWizard(models.TransientModel):
    _name= "create.maintenance.requests.wizard"
    _description= "Configure the maintenance requests to create from the current task."

    @api.model
    def _default_task_id(self):
        return self.env["project.task"].browse(self._context.get("active_ids"))


    name = fields.Char("Title", required=True)
    user_id = fields.Many2one('res.users', string='Technician')
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High')], string='Priority')
    maintenance_type = fields.Selection([('corrective', 'Corrective'), ('preventive', 'Preventive')], string='Maintenance Type', default="corrective")
    schedule_date = fields.Datetime('Scheduled Date')
    duration = fields.Float(help="Duration in hours.")
    description = fields.Html('Description')

    equipment_domain = fields.Char("Equipment Domain")

    task_id = fields.Many2one(
        "project.task",
        string="Task",
        required=True,
        default=_default_task_id,
    )

    @api.model
    def action_open_wizard(self):
        """
        Open the form view.
        """
        return {
            'name': _('Create maintenance requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'create.maintenance.requests.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }


    def create_maintenance_requests(self):
        """
        Create the maintenance requests with the data filled in the wizard form.
        """
        vals_list = self._compute_vals_list()
        maintenance_requests = self.env["maintenance.request"].sudo().create(vals_list)
        return self._get_action(maintenance_requests)


    def _compute_vals_list(self):
        """
        Compute the list of data to use for all the maintenance requests creation
        """
        equipment_list = self.env["maintenance.equipment"].search(safe_eval(self.equipment_domain))
        if len(equipment_list) == 0:
            raise UserError("No equipment is matching the domain. Maintenance request creation is not possible.")

        vals_list = []
        common_vals = {
            "name": self.name,
            "user_id": self.user_id.id,
            "priority": self.priority,
            "maintenance_type": self.maintenance_type,
            "schedule_date": self.schedule_date,
            "duration": self.duration,
            "description": self.description,
            "task_id": self.task_id.id,
            "project_id": self.task_id.project_id.id
        }

        for equipment in equipment_list:
            vals = common_vals.copy()
            vals["equipment_id"] = equipment.id
            vals_list.append(vals)

        return vals_list


    def _get_action(self, maintenance_requests):
        """
        Provide the action to go to the tree view of the maintenance requests created.
        """
        search_view_ref = self.env.ref('maintenance.hr_equipment_request_view_search', False)
        form_view_ref = self.env.ref('maintenance.hr_equipment_request_view_form', False)
        tree_view_ref = self.env.ref('maintenance.hr_equipment_request_view_tree', False)

        return  {
            'domain': [('id', 'in', maintenance_requests.ids)],
            'name': 'Maintenance Requests',
            'res_model': 'maintenance.request',
            'type': 'ir.actions.act_window',
            'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
            'search_view_id': search_view_ref and [search_view_ref.id],
        }
