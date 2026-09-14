from odoo import api, fields, models, _  # type: ignore


class LLPPayrollDraftConfirm(models.TransientModel):
    _name = 'llp.payroll.draft.confirm'
    _description = 'Цалин бодолтыг ноорог болгох баталгаажуулалт'

    payroll_id = fields.Many2one('llp.payroll', string="Цалин бодолт", readonly=True)
    move_count = fields.Integer(string="Холбоотой ажил гүйлгээний тоо", readonly=True)

    def action_confirm_cancel_moves(self):
        self.ensure_one()
        payroll = self.payroll_id
        payroll._cancel_related_moves()
        payroll._revert_debt_vacation_states()
        payroll.action_draft()
        return {'type': 'ir.actions.act_window_close'}

    def action_dismiss(self):
        return {'type': 'ir.actions.act_window_close'}
