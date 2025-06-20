from odoo import models, fields


class StateLog(models.Model):
    _name = "state.log"
    _description = "statelog"
    _order = 'create_date desc'


    name = fields.Char('Name')
    state_str = fields.Char(string="State")
    modified_date = fields.Datetime("Modified Date")
    elapsed_time = fields.Float("Elapsed Time")
    elapsed_time_live = fields.Float("Elapsed Time Live", compute="_compute_waiting_elapsed_time")
    content = fields.Char(string="Content")
    created_user_id = fields.Many2one("res.users", string="Created user")
    approved = fields.Integer("is approved", default=0)  # 0 if not dynamic workflow 1 if approved dynamic workflow 2 if refused dynamic workflow
    action_text = fields.Char('Action',help='Батласан эсэх юу хийсэн нь')
    log_type = fields.Char('Log Type')
    approver_type = fields.Char('Approver Type')


    def _compute_waiting_elapsed_time(self):
        for rec in self:
            rec.elapsed_time_live = (fields.datetime.now() - rec.modified_date).total_seconds() / 3600 if rec.content == "Хүлээгдэж буй" else rec.elapsed_time_live