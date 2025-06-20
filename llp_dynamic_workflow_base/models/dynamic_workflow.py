from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class DynamicWorkflow(models.Model):
    _name = 'dynamic.workflow'
    _description = 'Dynamic Workflow'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    state = fields.Selection([('draft', 'draft'), ('confirmed', 'confirmed')], 'state', default='draft')
    name = fields.Char('Name')
    model_id = fields.Many2one('ir.model', 'Model')
    model_name = fields.Char(related='model_id.model', string='Model Name', store=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    description = fields.Char('Description')
    line_ids = fields.One2many('dynamic.workflow.line', 'flow_id', 'Workflow lines', copy=True)
    active_line_ids = fields.Many2many('dynamic.workflow.line', compute="_compute_active_line_ids")
    min_seq = fields.Integer(compute="_compute_min_seq_num",store=True)
    department_ids = fields.Many2many('hr.department',string='Department', default=lambda self:[self.env.user.employee_id.department_id.id] if self.env.user.employee_id.department_id.id else False, tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, string='Currency')


    def _get_start_flow(self, id, name, model, model_description):
        if not self.mapped('active_line_ids'):
            return False
        line = min(self.mapped('active_line_ids'), key=lambda obj: obj.sequence)
        line._send_notif(id, name, model, model_description)
        return line
    
    @api.depends('line_ids')
    def _compute_active_line_ids(self):
        for rec in self:
            rec.active_line_ids = rec.mapped('line_ids').filtered(lambda line: line.is_active == True)

    @api.depends('line_ids')
    def _compute_min_seq_num(self):
        for rec in self:
            seq = [line.sequence for line in rec.line_ids]
            rec.min_seq = min(seq) if seq else 0
            
    def unlink(self):
        for rec in self:
            rec._check_if_used('dynamic_id')
            rec._check_if_used('workflow_id')
        return super(DynamicWorkflow, self).unlink()
    
    def is_unique_list(self,lst):
        if lst:
            return len(lst) == len(set(lst))
        else:
            return True

    @api.constrains('line_ids')
    def _check_line_ids_seq(self):
        for rec in self:
            seq = [line.sequence for line in rec.line_ids]
            if not self.is_unique_list(seq):
                raise ValidationError('Төлөвийн мөр дэх дараалал буруу байна')
            
    #Эхний төлөв рүү шилжүүлэхэд ашиглах
    def _get_first_flow(self, id, name, model, model_description):
        if not self.mapped('active_line_ids'):
            return False
        line = min(self.mapped('active_line_ids'), key=lambda obj: obj.sequence)
        return line
class LineDynamicState(models.Model):
    _name = 'line.dynamic.state'
    _description = 'Dynamic state line'
    _order = 'sequence'

    workflow_line_id = fields.Many2one('dynamic.workflow.line', 'Workflow Line')
    dynamic_state = fields.Many2one('dynamic.state', 'Dynamic State')
    sequence = fields.Integer('Sequence')

    def name_get(self):
        result = []
        for record in self:
            name = record.dynamic_state.name
            result.append((record.id, name))
        return result